# hello-blog

A demo repository used by the Grape DevOps platform (dev environment) for
end-to-end pipeline verification: VOD -> Issue -> Coding -> QA -> SRE.

## Layout (created by the coding agent)

- `app/` — Flask app (REST + WebSocket danmaku on the same port)
- `tests/` — pytest suite
- `docs/` — design notes produced per issue

This initial commit only bootstraps the `main` branch so the platform can
clone the repository and create feature branches. See the issue tracker for
the actual feature work.

e2e-11220517
