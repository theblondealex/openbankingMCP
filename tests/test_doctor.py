from openbankingmcp import doctor


def test_doctor_does_not_contact_truelayer_in_offline_mode(monkeypatch):
    monkeypatch.setattr(doctor, "dashboard_is_running", lambda: True)
    monkeypatch.setattr(doctor.Path, "is_file", lambda _path: True)
    monkeypatch.setattr("sys.argv", ["openbanking-mcp-doctor", "--offline"])
    doctor.main()


def test_doctor_does_not_print_provider_error_details(monkeypatch):
    class Keychain:
        def get(self, name):
            return "live-client" if name.endswith("id") else "live-secret"

    monkeypatch.setattr(doctor.TrueLayer, "token", lambda _self: (_ for _ in ()).throw(RuntimeError("live-secret")))
    ok, message = doctor.credentials_work(Keychain())
    assert not ok
    assert "live-secret" not in message
    assert "could not verify" in message
