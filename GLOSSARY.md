# Domain Glossary

Domain concepts for Blogger Auto-Pilot SaaS.

### Tenant
An authenticated publisher account with an isolated workspace, subscription plan, and usage credits.

### Blog
A connected Google Blogger publication destination identified by a Blog ID, credentials, and niche settings.

### Keyword
A targeted search query planned or in-progress for autonomous article drafting.

### Article
A drafted or published blog post with title, meta description, HTML content, structured FAQ schema, and lifecycle status (`draft`, `approved`, `published`).

### Subscription
A commercial plan record mapping a tenant to an article credit quota, connected blog limit, and Midtrans billing state.

### Autopilot Cycle
A periodic background execution that selects active tenants with available quota, claims planned keywords, and drafts articles.

### Content Generator
A deep module encapsulating prompt synthesis, LLM generation behind an interchangeable adapter, schema audit injection, atomic tenant quota deduction, and article drafting.
