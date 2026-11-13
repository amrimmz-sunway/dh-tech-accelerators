# Angular / Ionic unit

**Unit:** one page or feature: a component (or Ionic page), a data service, a route entry, and the module wiring the repo uses. Add a model/interface and a spec where the exemplar has them.

## Read before writing
- The exemplar's component/page `.ts`, `.html` and `.scss`, its service, its routing module or `*.routes.ts`, and its spec.
- The Angular version (`framework_version` from detect). It decides **standalone vs NgModule**:
  - Angular 8–13: NgModule, with `*-routing.module.ts` and a lazy `loadChildren: () => import(...).then(m => m.XModule)`.
  - Angular 14–16: either; follow the exemplar.
  - Angular 17+: usually standalone components and `app.routes.ts` / `provideRouter`. Follow the exemplar.
- The HTTP pattern: services wrapping `HttpClient`, environment `apiUrl`, interceptors for auth.

## Write
- **Prefer the CLI** so the files match the project's schematics: `npx ng generate component <path> [--standalone]`, `npx ng generate service <path>`, or Ionic `npx ionic generate page <path>`. Run it only after showing the user the command. Then edit the generated files to match the exemplar (inject style, `inject()` vs constructor, signals vs RxJS, UI library such as PrimeNG or Ionic components).
- If the CLI isn't installed or fails, write the files by hand, mirroring the exemplar.
- A route entry in the same routing file and style (lazy vs eager) as the exemplar's siblings.
- Service methods that use the existing environment base URL and typed models.

## Security (always)
- **API base URLs come from `environment*.ts`.** Never hardcode hosts. Never put keys or tokens in `environment*.ts`; they ship to the browser.
- **No `innerHTML` bindings or `bypassSecurityTrust*`** unless the exemplar has a reviewed reason; flag it if copied.
- Route guards: protected pages get the same `canActivate` guard as their siblings.
- Auth tokens go through the existing interceptor. Don't attach headers by hand in the new service.

## Verify
`npx ng build` (or `npm run build`). Then `npm test -- --watch=false --browsers=ChromeHeadless` if Karma is set up and Chrome is available; otherwise say tests weren't run. Run lint if a script exists.
