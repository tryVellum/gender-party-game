# Generated browser dependency

`build/build_release.ps1` downloads `socket.io.min.js` into this directory before the Windows package is built. The generated JavaScript file is intentionally excluded from Git because the source pages retain a CDN fallback for development.
