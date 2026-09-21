# ListenBrainz Scrobbler for ONDA

External `python-v1` scrobbling provider for ONDA. It sends `playing_now` and
qualified listens to ListenBrainz without adding service-specific code to the
application.

## Configuration

Open the plugin configuration and press **Conectar con ListenBrainz**. Sign in,
copy the user token shown by ListenBrainz, then return to ONDA and confirm the
import. ONDA stores the token encrypted in plugin-isolated storage.

1. Sign in to ListenBrainz.
2. Open `https://listenbrainz.org/settings/` and copy the user token.
3. Install the `.meb` in ONDA.
4. Open the plugin settings, paste the token and press **Probar**.

ONDA stores the token in its encrypted, plugin-isolated storage. The provider
does not write it to files, logs, errors or API responses.

## Build

From the ONDA repository:

```powershell
dart run .\tools\meb_cli\bin\meb.dart validate ..\onda-listenbrainz-scrobble-provider
dart run .\tools\meb_cli\bin\meb.dart build ..\onda-listenbrainz-scrobble-provider
```

## Test

```powershell
python -m unittest discover -s .\tests -v
```
