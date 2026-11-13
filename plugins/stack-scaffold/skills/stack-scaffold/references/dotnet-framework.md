# .NET Framework (ASP.NET MVC / Web API) unit

**Unit:** one resource: a controller, a service (+ interface if the repo uses DI), a model/DTO, and a repository if present. MVC web projects also get views under `Views/<Name>/`.

These solutions often hold several projects (Web, API, Services). **First ask which project the new controller goes in.** Then use exemplar files from that same project and its referenced service project. Never mix patterns across projects.

## Read before writing
- The exemplar controller in the target project, its service and interface, model/DTO, and views.
- The DI registration (Unity/Autofac/Ninject config, `BindExtensions`, `App_Start/*`) and the route config (`RouteConfig.cs`, `WebApiConfig.cs`, attribute routing).
- The data access style: Dapper, EF6 `DbContext`, ADO.NET with `SqlCommand`/`MySqlCommand`.
- The `.csproj` format. Old-style (non-SDK) projects list every file in `<Compile Include="..." />`, and views in `<Content Include="..." />`.

## Write
- C# files mirroring the exemplar's namespace, folder, base class (`Controller`, `ApiController`, a custom base), attributes (`[Authorize]`, `[RoutePrefix]`), and async style.
- **Add every new `.cs` file to the right `.csproj`** as `<Compile Include="Folder\File.cs" />`, and views as `<Content Include="Views\Name\Index.cshtml" />`. Put them next to the exemplar's entries. Without this, old-style projects don't compile the file.
- A DI registration line next to the exemplar's.
- Views copied from the exemplar's views (layout, helpers, anti-forgery tokens).

## Security (always)
- **Parameterised SQL only**: `SqlParameter`/`MySqlParameter`, Dapper parameters, or EF. Never concatenate SQL, even if the exemplar does; flag it with file and line.
- `[ValidateAntiForgeryToken]` on MVC POST actions if the exemplar's POSTs have it, and `[Authorize]` matching siblings.
- Validate models (`ModelState.IsValid`, data annotations) before using input.
- No connection strings or keys in code. Use `ConfigurationManager.AppSettings` / `ConnectionStrings` names that already exist, and tell the user about any new key needed in `Web.config` transforms. Never write secret values into `Web.config`.

## Verify
On Windows with Visual Studio Build Tools: `msbuild <sln> /p:Configuration=Debug /verbosity:minimal`. On macOS/Linux msbuild for .NET Framework web projects usually isn't available. In that case, check that every new file is listed in the `.csproj`, that the namespaces match, and that the braces balance. Tell the user the build is **unverified** and must be built on Windows or in CI.
