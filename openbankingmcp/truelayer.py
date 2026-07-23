"""Narrow TrueLayer Data client; no payment endpoints are permitted."""
from __future__ import annotations
import httpx
import re
from urllib.parse import urlencode
from urllib.parse import urlparse

class ReauthorizationRequired(Exception): pass
class ProviderUnavailable(Exception): pass
class EndpointNotSupported(Exception): pass
class ProhibitedEndpoint(Exception): pass


_ALLOWED_ENDPOINTS = (
    ("POST", "auth.truelayer.com", re.compile(r"/connect/token")),
    ("DELETE", "auth.truelayer.com", re.compile(r"/api/delete")),
    ("POST", "api.truelayer.com", re.compile(r"/v3/data-connections")),
    ("GET", "api.truelayer.com", re.compile(r"/v3/connected-accounts")),
    ("GET", "api.truelayer.com", re.compile(r"/data/v1/me")),
    ("GET", "api.truelayer.com", re.compile(r"/data/v1/accounts")),
    ("GET", "api.truelayer.com", re.compile(r"/data/v1/accounts/[^/]+/(?:balance|transactions(?:/pending)?)")),
    ("GET", "api.truelayer.com", re.compile(r"/data/v1/cards")),
    ("GET", "api.truelayer.com", re.compile(r"/data/v1/cards/[^/]+/(?:balance|transactions(?:/pending)?)")),
)


def endpoint_allowed(method: str, url: str) -> bool:
    parsed=urlparse(url)
    return any(method.upper() == allowed_method and parsed.netloc == host and pattern.fullmatch(parsed.path) for allowed_method,host,pattern in _ALLOWED_ENDPOINTS)

class TrueLayer:
    def __init__(self, client_id, client_secret):
        self.client_id, self.client_secret = client_id, client_secret
        self.base = "https://api.truelayer.com"
        self.auth_base = "https://auth.truelayer.com"
    def _request(self, method, url, **kwargs):
        if not endpoint_allowed(method,url): raise ProhibitedEndpoint(f"TrueLayer endpoint is outside the read-only allowlist: {method.upper()} {urlparse(url).path}")
        response=httpx.request(method,url,timeout=20,**kwargs)
        if response.status_code==400:
            try: error=response.json().get("error")
            except Exception: error=None
            if error in {"invalid_grant","access_denied"}: raise ReauthorizationRequired()
        if response.status_code in {401,403}: raise ReauthorizationRequired()
        if response.status_code==429: raise ProviderUnavailable("rate_limited")
        if response.status_code==501: raise EndpointNotSupported()
        if response.status_code>=500: raise ProviderUnavailable("provider_unavailable")
        response.raise_for_status(); return response
    def token(self):
        return self._request("POST",self.auth_base+"/connect/token",data={"grant_type":"client_credentials","scope":"data","client_id":self.client_id,"client_secret":self.client_secret}).json()["access_token"]
    def create_connection(self, user, redirect_uri):
        return self._request("POST",self.base+"/v3/data-connections",headers={"Authorization":"Bearer "+self.token()},json={"provider_selection":{"type":"user_selected","filter":{"countries":["GB"],"release_channel":"public","customer_segments":["retail"]}},"hosted_page":{"type":"authorization_flow","redirect":{"return_uri":redirect_uri}},"scopes":["accounts","balance","transactions"],"user":user,"user_consent":{"type":"authorization_flow_captured"},"data_access_type":"recurring"}).json()
    def accounts(self, connection_id):
        return self._request("GET",self.base+"/v3/connected-accounts",headers={"Authorization":"Bearer "+self.token(),"Connection-Id":connection_id}).json().get("items",[])
    def v1_auth_link(self, redirect_uri, state):
        return self.auth_base + "/?" + urlencode({"response_type":"code","client_id":self.client_id,"redirect_uri":redirect_uri,"scope":"accounts cards balance transactions offline_access","state":state})
    def exchange_code(self, code, redirect_uri):
        return self._request("POST",self.auth_base+"/connect/token",data={"grant_type":"authorization_code","client_id":self.client_id,"client_secret":self.client_secret,"redirect_uri":redirect_uri,"code":code}).json()
    def refresh(self, refresh_token):
        return self._request("POST",self.auth_base+"/connect/token",data={"grant_type":"refresh_token","client_id":self.client_id,"client_secret":self.client_secret,"refresh_token":refresh_token}).json()
    def v1_get(self, access_token, path, params=None):
        return self._request("GET",self.base+"/data/v1/"+path,headers={"Authorization":"Bearer "+access_token},params=params).json()
    def v1_accounts(self, access_token):
        return self.v1_get(access_token,"accounts").get("results",[])
    def v1_cards(self, access_token):
        return self.v1_get(access_token,"cards").get("results",[])
    def connection_metadata(self, access_token):
        return self.v1_get(access_token,"me").get("results",[{}])[0]
    def delete_credential(self, access_token):
        try:
            self._request("DELETE",self.auth_base+"/api/delete",headers={"Authorization":"Bearer "+access_token})
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 404: raise
    def balance(self, access_token, account_id):
        return self.v1_get(access_token,f"accounts/{account_id}/balance").get("results",[{}])[0]
    def transactions(self, access_token, account_id, start, end):
        return self.v1_get(access_token,f"accounts/{account_id}/transactions",{"from":start,"to":end}).get("results",[])
    def pending_transactions(self, access_token, account_id):
        try:
            return self.v1_get(access_token,f"accounts/{account_id}/transactions/pending").get("results",[])
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404: return []
            raise
    def card_balance(self, access_token, account_id):
        return self.v1_get(access_token,f"cards/{account_id}/balance").get("results",[{}])[0]
    def card_transactions(self, access_token, account_id, start, end):
        return self.v1_get(access_token,f"cards/{account_id}/transactions",{"from":start,"to":end}).get("results",[])
    def card_pending_transactions(self, access_token, account_id):
        try:
            return self.v1_get(access_token,f"cards/{account_id}/transactions/pending").get("results",[])
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404: return []
            raise
