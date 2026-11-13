# Choosing the Node and Java version

Use the version production runs. If the repo doesn't say (no `.nvmrc`, `engines` or Dockerfile `FROM node:`), ask the user, and use this table to sanity-check the answer. A CI Node version newer than the framework supports is the most common cause of a red first run.

| Framework (from package.json) | Node versions it supports | Notes |
|---|---|---|
| Angular 8 / Ionic 5 | 10, 12 | Node 12 is long out of support. Suggest an upgrade ticket, but match it in CI so the build is green. |
| Angular 12–14 | 12.20+, 14, 16 (14 needs 14.15+) | |
| Angular 15–16 | 16, 18 (15 also allows 14.20+) | |
| Angular 17–18 | 18.13+, 20 | |
| Angular 19 | 18.19+, 20.11+, 22 | |
| Angular 20 | 20.19+, 22.12+, 24 | |
| React Native 0.72 | 16, 18 | JDK 11 or 17 |
| React Native 0.73–0.75 | 18+ | JDK 17 |
| React Native 0.76+ | 18.18+, 20+ (check `engines`) | JDK 17 |
| Express 4.x | any current LTS | match the Dockerfile/production image |

If the framework's supported versions don't include a currently supported Node LTS, generate the workflow with the old version. Then tell the user in one line that the runtime is past its end of life.
