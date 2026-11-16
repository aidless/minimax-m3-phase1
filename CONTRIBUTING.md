# Contributing

Thanks for your interest in improving this repository.

## Getting set up

```bash
git clone https://github.com/aidless/minimax-m3-phase1.git
cd minimax-m3-phase1
make check
```

`make check` uses the Python 3 standard library only. `requirements.txt` is for the
optional PDF path and is not part of the offline check.

## Verifying your change

`make check` is the same command CI runs. Please run it before opening a pull request.

## Pull requests

- One logical change per pull request.
- Explain what breaks or is missing without the change.
- State how you verified it, and paste the command output.
- Keep unrelated reformatting out of the diff.

## Security

Do not open a public issue for a security problem. Use the private channel described
in [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
