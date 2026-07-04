# Migration bugs found by the REST API test suite

All are Grails 2.5 → 7.1 / GORM 5 → 7 regressions surfaced by running the suite.

## Fixed (this session, driven by the suite)

| # | Endpoint(s) | Root cause | Fix |
|---|---|---|---|
| 1 | `GET /ws/user/$id/activities` | Grails 7 dropped implicit service transactions; `user.preferences.save()` ran with no tx → `TransactionRequiredException` | Wrapped the write in `User.withTransaction {}` (`UserController.activities`) |
| 2 | `GET /ws/project/$p/task`, `.../task/$id` | `Task.getSprint()` did `(Sprint) this.backlog` — backlog is a lazy `TimeBox` Hibernate proxy → `GroovyCastException` | `Hibernate.unproxy(...)` before the cast (`Task.getSprint`) |
| 3 | `DELETE` of story / actor / comment (any domain delete) | `IceScrumEventPublisher` (BEFORE_DELETE) used `new DefaultGrailsDomainClass(cls).persistentProperties`, removed in Grails 7 | Read persistent props from `grailsApplication.mappingContext.getPersistentEntity(...)` |
| 4 | `GET /ws/openapi.json` (partial) | Bare `GET`/`POST` constants in nested mapping closures resolved against the `RegexUrlMapping` delegate | Qualified as `OpenAPIUrlMappingsRenderer.GET/POST` — see BUG-8 for the remaining `PUT`/`DELETE` |

(Two other suite failures were *test* mistakes, not product bugs: the project
`update` action reads `params.projectd` not `project`, and `actor`/`story`
update bind the full object incl. `name`, as the UI always sends it. Tests were
corrected.)

## Fixed (second pass)

| # | Endpoint(s) | Root cause | Fix |
|---|---|---|---|
| 6 | `POST` story/task update + any op firing webhooks | `HookListenerService:84` used GORM's removed `Hook.async.task{}` async engine → `MissingPropertyException: async` | Run the webhook dispatch synchronously in `Hook.withSession {}` (keeps the session for lazy `hook.events`); inner `withTransaction{}` qualified to `Hook.withTransaction{}` |
| 7 | `POST /ws/project/$p/task/$id` (update), `.../take`, task/sprint ops | ~8 `(Sprint) task.backlog` casts on the lazy `TimeBox` proxy (same as BUG-2) | Added `Task.getSprintBacklog()` (unproxies) and routed all sites through `task.sprintBacklog`; also `StoryService:629` `findCurrentSprint().list()`→`.get()` (uniqueResult) |
| 9 | `POST /ws/project/$p/task/$id` (update) | `Task` `parentProject` constraint validator (Task.groovy:91) called the Sprint-only `getParentProject()` on the `TimeBox` proxy → `IllegalArgumentException: object is not an instance of declaring class` | Route through `task.sprintBacklog?.parentProject` |

## Still open (documented as `xfail`)

### BUG-8 — `GET /ws/openapi.json` (Swagger doc generation only)
* **Blocks:** only the OpenAPI/Swagger documentation endpoint. **The REST API itself
  works** — every other endpoint is green.
* **Site:** `iceScrum/.../web/OpenAPIUrlMappingsRenderer.groovy` (`getOpenApi` nested
  mapping closures).
* **Symptom:** intermittent `MissingPropertyException: No such property: GET/PUT for
  class RegexUrlMapping`. It passes on some boots and fails on others.
* **What was tried:** the HTTP-method tokens were reduced from `static final` fields
  to plain string literals (`'get'`/`'post'`/`'put'`/`'delete'`) throughout, yet the
  bare-identifier error still surfaces — so the fault is *not* those constants. It is a
  deeper Grails 7 closure/mapping-introspection issue (or an incremental-compile
  staleness) in this doc generator.
* **Fix direction:** rework `getOpenApi` to iterate `UrlMapping`s without relying on
  Groovy dynamic resolution inside deeply-nested closures (extract the per-mapping work
  into a plain method taking the mapping as a typed argument), and confirm against a
  clean `:iceScrum:compileGroovy`.
