# React Native unit

**Unit:** one screen or feature. That's the screen component(s), the API call for its data, and its navigation registration. Add state (Redux slice or saga, context) and a test only where the exemplar has them.

Two layouts are common. Follow whichever the exemplar uses:
- **Feature folders:** `src/app/<feature>/main.tsx` (+ sub-screens), with `API/<feature>/index.js` for calls.
- **Flat:** `src/screens/<Name>Screen.tsx`, with `src/services/api.ts` for calls.

## Read before writing
- The exemplar's screen files, API module, and state files (slice/saga/toolkit) if present.
- The navigator file from `registration_files` (`createNativeStackNavigator`, `<Stack.Screen>`, tab navigators) and the route-params type file (for example `types/navigation.ts`) if TS.
- The shared HTTP client (axios instance or fetch wrapper), and how it attaches auth tokens and base URLs.
- Shared UI: layout wrappers, theme/colors, i18n helper. Use them; don't restyle from scratch.

## Write
- The screen in the exemplar's language (JS vs TSX), component style (function + hooks vs class), and styling approach (StyleSheet, styled-components, theme tokens).
- The API function in the existing API module or a sibling, using the **shared client**. Never use a new `fetch` with a hardcoded base URL.
- A navigation entry in the same navigator, plus the params type if the repo types its routes.
- State wiring only if the exemplar's feature has it.
- A Jest test if `__tests__/` exists. A render test with the API mocked, like the exemplar's.

## Security (always)
- **No base URLs, keys or tokens in code.** Use the repo's config (`app-config.js`, `react-native-config`, env files). Never copy values from one environment file to another.
- **If the shared client itself hardcodes the base URL** (no config mechanism exists), reuse the client as-is, and flag the hardcoding in the close. Don't add a config system as part of a scaffold.
- **Tokens go through the existing secure storage helper** (Keychain/Keystore wrapper). Never use plain AsyncStorage for credentials, even if the exemplar does; flag it if it does.
- Don't log request or response bodies that may hold personal or health data.
- Don't touch signing files, `google-services.json`, `GoogleService-Info.plist`, or bundle IDs.

## Verify
`npm run lint` and `npm test` if they exist, and `npx tsc --noEmit` for TS repos. If `tsc` was already failing before your change, compare the error count before and after and report only new errors. Don't run the app or build native code unless the user asks.
