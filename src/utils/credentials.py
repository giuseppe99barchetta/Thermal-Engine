"""Network secrets live in an OS credential store, never a plaintext fallback."""
import uuid

SERVICE = "ThermalEngine.NetworkSensors"
SECRET_FIELDS = ("password", "token")


def get_backend():
    try:
        import keyring
        backend = keyring.get_keyring()
        candidates = backend.backends if type(backend).__module__ == "keyring.backends.chainer" else [backend]
        trusted = ("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService",
                   "keyring.backends.libsecret", "keyring.backends.kwallet")
        for candidate in candidates:
            if type(candidate).__module__ in trusted and candidate.priority > 0:
                return candidate
    except Exception:
        pass
    raise RuntimeError("No unlocked OS credential store is available. Install keyring and configure your system's credential store.")


def resolve_sources(sources):
    result = []
    backend = None
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Each sensor configuration must be an object.")
        config = dict(source)
        for field in SECRET_FIELDS:
            reference = config.get(field + "_ref")
            if reference:
                try:
                    backend = backend or get_backend()
                    value = backend.get_password(SERVICE, reference)
                except Exception:
                    raise RuntimeError("Unable to read saved sensor credentials from the OS store.") from None
                if value is None:
                    raise RuntimeError("A saved sensor credential is missing. Re-enter it in Network Sensors.")
                config[field] = value
        result.append(config)
    return result


def protect_sources(sources):
    """Return sanitized settings and new entries to roll back if file saving fails."""
    result, created = [], []
    backend = None
    try:
        for source in sources:
            config = dict(source)
            for field in SECRET_FIELDS:
                secret = config.pop(field, "")
                previous = config.pop(field + "_ref", None)
                if not secret:
                    continue
                backend = backend or get_backend()
                if previous and backend.get_password(SERVICE, previous) == secret:
                    reference = previous
                else:
                    reference = uuid.uuid4().hex
                    created.append(reference)
                    backend.set_password(SERVICE, reference, secret)
                    if backend.get_password(SERVICE, reference) != secret:
                        raise RuntimeError("Credential store did not retain the secret.")
                config[field + "_ref"] = reference
            result.append(config)
    except Exception:
        delete_references(created, backend)
        raise RuntimeError("Could not save sensor credentials in the OS store. Existing settings were preserved.") from None
    return result, created


def references(sources):
    return {s[field + "_ref"] for s in sources for field in SECRET_FIELDS if s.get(field + "_ref")}


def delete_references(entries, backend=None):
    if not entries:
        return
    try:
        backend = backend or get_backend()
    except RuntimeError:
        return
    for reference in entries:
        try:
            backend.delete_password(SERVICE, reference)
        except Exception:
            pass  # Keep settings usable if a previous credential was already removed.
