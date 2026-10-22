# Stability Policy

## Versioning

We largely copy what Python does for versioning, i.e.:

- Major version is only sparingly incremented, reserved for very big changes or
  significant reworks.
- We do breaking changes in minor releases.
- Patch releases are only for fixes.

## Scope

- Changes to the CLI interface are subject to the breaking changes procedure.
- There are currently no stability guarantees for pmbootstrap's internal API.

## Breaking changes

When we do a breaking change, it is handled as such:

- The feature gets deprecated for 1 minor release and using it results in a
  warning being printed.
- In the next minor release after that one, the breaking change is made.
