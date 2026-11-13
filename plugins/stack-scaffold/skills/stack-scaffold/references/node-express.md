# Node / Express unit

**Unit:** one resource or endpoint group. The usual layers are route, controller, service, plus repository/model and validation **if the repo has them**. Don't add a layer the exemplar doesn't use: a repo where routes call the DB directly gets the same shape, plus one flagged suggestion.

## Read before writing
- The exemplar's route, controller, service, validation and model files, all of them.
- The registration file (`app.use(...)` / router index) from `registration_files`.
- How config is read (`process.env.X`, a `config/` module, `dotenv`), using the **masked grep** from SKILL.md: never print DB config files. And how errors propagate (`next(err)`, a custom error class, response helpers).
- The DB access style: `mysql2`/`mssql`/`pg` query helpers, Sequelize/Mongoose models, or raw pools.

## Write
- New files mirroring the exemplar's paths, naming case (`cardTemplateController.js` vs `card-template.controller.js`), module system (CommonJS `require` vs ESM `import`), and exported shape.
- A route registration line in the same file and style as the existing ones, and in the same position (alphabetical or grouped).
- A migration (up and down) mirroring the newest one in `migration_dirs`, if the unit needs a new table.
- A test next to the exemplar's tests if the repo has a test runner (`node --test`, mocha, jest). Cover the service layer with the DB stubbed, the same way the exemplar's test does.

## Security (always)
- **Queries are parameterised**: `?`/`$1` placeholders or ORM methods. Never build SQL with string concatenation or template literals, even if the exemplar does. If it does, flag it to the user with the file and line.
- **Validate request input at the route boundary**, using the repo's validator (Joi, express-validator, a schema folder). If the repo has none, validate types and lengths by hand in the controller, and say so.
- No secrets, tokens or connection strings in code. Read from `process.env`; add any new variable name to `.env.example` (create it only if the repo already uses one).
- Respect the exemplar's auth middleware: protected resources get the same middleware chain.
- Return errors without stack traces or SQL messages to the client.

## Verify
`npm test` if a test script exists, plus `node --check <file>` on each new JS file. If the server can start without external services, run `node -e "require('./<entry>')"`. Otherwise say that startup is unverified.
