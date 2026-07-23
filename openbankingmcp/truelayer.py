"""Narrow TrueLayer Data v3 client; no payment endpoints are present."""
from __future__ import annotations
import httpx
from urllib.parse import urlencode

class ReauthorizationRequired(Exception): pass
class ProviderUnavailable(Exception): pass

class TrueLayer:
    def __init__(self, client_id, client_secret):
        self.client_id, self.client_secret = client_id, client_secret
        self.base = "https://api.truelayer.com"
        self.auth_base = "https://auth.truelayer.com"
    def _request(self, method, url, **kwargs):
        response=httpx.request(method,url,timeout=20,**kwargs)
        if response.status_code in {401,403}: raise ReauthorizationRequired()
        if response.status_code==429: raise ProviderUnavailable("rate_limited")
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
    def balance(self, access_token, account_id):
        return self.v1_get(access_token,f"accounts/{account_id}/balance").get("results",[{}])[0]
    def transactions(self, access_token, account_id, start, end):
        return self.v1_get(access_token,f"accounts/{account_id}/transactions",{"from":start,"to":end}).get("results",[])
    def card_balance(self, access_token, account_id):
        return self.v1_get(access_token,f"cards/{account_id}/balance").get("results",[{}])[0]
    def card_transactions(self, access_token, account_id, start, end):
        return self.v1_get(access_token,f"cards/{account_id}/transactions",{"from":start,"to":end}).get("results",[])
