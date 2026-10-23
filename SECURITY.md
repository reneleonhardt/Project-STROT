# Security

## Reporting a vulnerability

Please report security issues privately to **lee@strot-ai.xyz** rather than
opening a public issue. Include steps to reproduce and the affected version.
You'll get an acknowledgement, and a fix or mitigation plan once it's confirmed.

## Supported versions

Fixes land on the latest release on PyPI (`pip install strot-ai`). Please upgrade
before reporting.

## Security model

A few things worth knowing about how STROT handles generated code and untrusted
input:

- **Code is generated once, at compile time — never at runtime.** The compiled
  artifact is a frozen Python file; production runs it as-is and generates
  nothing new, so there is no runtime code generation to exploit.
- **Synthesized code is linted before it's accepted.** The compiler rejects an
  artifact whose generated code reaches for the network, filesystem, processes,
  or dynamic execution (`eval`/`exec`/`open`/`__import__`), or imports arbitrary
  packages. A compile that trips the lint fails rather than serving.
- **The compile step calls an external LLM.** Your API key and the records in
  your compile sample go to whichever provider you configure. Treat that sample
  as data you're sending to that provider, and keep your key in the environment
  or a secret store, not in source.
- **Runtime stays local.** A warm production box decides with the local model
  and no outbound calls, so no key or network access is needed to serve.

If you're embedding STROT in a product, review the compiled artifact the way you
would any generated code before shipping it.
