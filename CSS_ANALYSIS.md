# Common CSS Analysis: Account, Courses, Students, Assistant Apps

## Overview
This document analyzes common CSS codes used across the account, courses, students, and assistant apps in the e-learning platform. It identifies shared CSS tags/classes, their definitions, usage locations, and which modules depend on them.

---

## 1. DESIGN TOKENS & FOUNDATION CSS

### File Location
- **Primary**: `edu/courses/static/courses/css/tokens.css`
- **Main CSS**: `edu/courses/static/courses/css/main.css`
- **Reset**: `edu/courses/static/courses/css/reset.css`
- **Utilities**: `edu/courses/static/courses/css/utilities.css`

### Common CSS Variables (Design System)

#### Color Tokens
```css
--color-primary: #1f7a4e;           /* Primary brand color */
--color-primary-hover: #18613e;     /* Primary hover state */
--color-secondary-surface: #eaf5ef; /* Secondary background */
--color-accent: #2a6fb3;            /* Accent color */
--color-warning: #a06a00;           /* Warning state */
--color-error: #b3261e;             /* Error state */
--color-text: #1b2630;              /* Text color */
--color-text-muted: #51606f;        /* Muted text */
--color-border: #c9d5df;            /* Border color */
--color-bg: #f4f7fa;                /* Background */
--color-surface: #ffffff;           /* Surface/card background */
--color-surface-soft: #f8fbfd;      /* Soft surface */
--color-focus-ring: (accent mix)    /* Focus state */
--color-shadow: 15 23 42;           /* Shadow RGB values */
```

#### Spacing Tokens
```css
--space-1: 0.25rem;    /* 4px */
--space-2: 0.5rem;     /* 8px */
--space-3: 0.75rem;    /* 12px */
--space-4: 1rem;       /* 16px */
--space-5: 1.5rem;     /* 24px */
--space-6: 2rem;       /* 32px */
--space-7: 3rem;       /* 48px */
```

#### Typography Tokens
```css
--font-body: "Sora", "Segoe UI", sans-serif;
--font-heading: "Sora", "Segoe UI", sans-serif;
--font-mono: "IBM Plex Mono", "Cascadia Mono", ...;
--fs-0: 0.875rem;      /* Small text */
--fs-1: 1.2rem;        /* Base text */
--fs-2: 1.2rem;        /* Medium text */
--fs-3: 1.44rem;       /* Large text */
--fs-4: 1.728rem;      /* Extra large */
--fs-5: 2.074rem;      /* Heading */
--lh-reading: 1.6;     /* Reading line height */
--lh-ui: 1.42;         /* UI line height */
```

#### Border Radius Tokens
```css
--radius-sm: 8px;
--radius-md: 12px;
--radius-lg: 16px;
```

#### Layout Tokens
```css
--rail-left: 280px;           /* Left sidebar width */
--rail-right: 380px;          /* Right sidebar width */
--rail-left-compact: 232px;   /* Compact left sidebar */
--course-modules-min: 220px;  /* Module panel min width */
--course-modules-max: 280px;  /* Module panel max width */
--topbar-height: 74px;        /* Header height */
--main-max: 1100px;           /* Main content max width */
--reading-max: 65ch;          /* Reading content max width */
--bp-sm: 640px;               /* Small breakpoint */
--bp-md: 900px;               /* Medium breakpoint */
--bp-lg: 1200px;              /* Large breakpoint */
--bp-xl: 1440px;              /* Extra large breakpoint */
```

### Where Used
| Module | File | Usage |
|--------|------|-------|
| **Courses** | base.html | Global foundation for all course pages |
| **Account** | account/base.html | Inherited through layout |
| **Assistant** | llm.html | Sidebar components use tokens |
| **Students** | All detail/list pages | Card and grid layouts |
| **Learning Insights** | base.html | Component styling |
| **Chat** | room.html | Message styling |

**Theme Variants:**
- `body.theme-dark` - Dark mode color adjustments
- `body.app-body--modern` - Modern design variant (Manrope font, updated colors)

---

## 2. COMMON UTILITY CLASSES

### Utility Classes

#### `.u-sr-only` (Screen Reader Only)
**Purpose**: Hide element visually but keep it accessible to screen readers
**File**: `courses/static/courses/css/utilities.css`
**Definition**:
```css
.u-sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}
```
**Used In**:
- Account authentication forms (skip links)
- Course navigation labels
- Accessibility labels throughout

#### `.hidden`
**Purpose**: Hide element with display: none
**File**: `courses/static/courses/css/utilities.css`
**Definition**:
```css
.hidden {
    display: none !important;
}
```
**Used In**: Dynamic UI elements (modals, panels)

---

## 3. LAYOUT COMPONENT CLASSES

### Layout Grid System

#### `.app-body`
**Purpose**: Root body container for all pages
**File**: `courses/static/courses/css/layout.css`
**Definition**:
```css
.app-body {
    --util-width: var(--rail-right);
    --rail-left-current: var(--rail-left);
    --workspace-modules-min-current: var(--course-modules-min);
    --workspace-modules-max-current: var(--course-modules-max);
}
```
**Used In**: All templates (courses, account, assistant, students)
**Modifiers**:
- `.app-body.has-assistant` - When AI sidebar is open
- `.app-body--modern` - Modern design theme

#### `.l-shell`
**Purpose**: Main layout container (grid with 3 columns)
**File**: `courses/static/courses/css/layout.css`
**Definition**:
```css
.l-shell {
    max-width: 1700px;
    display: grid;
    gap: var(--space-4);
    grid-template-columns: var(--rail-left-current) minmax(0, 1fr) var(--util-width);
    align-items: start;
    transition: grid-template-columns 0.2s ease;
    width: 100%;
}
```
**Used In**: Course detail, course list, manage pages
**Child Containers**:
- `.l-rail` - Left/right sidebars
- `.l-main` - Main content area
- `.l-util` - Utility/right sidebar

#### `.l-rail` (Left & Right)
**Purpose**: Sticky sidebar columns
**File**: `courses/static/courses/css/layout.css`
**Definition**:
```css
.l-rail--left {
    position: sticky;
    top: calc(var(--topbar-height) + var(--space-4));
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - var(--topbar-height) - (2 * var(--space-4)));
    gap: var(--space-4);
}
```
**Used In**: Courses with module sidebar, learning insights

#### `.l-main`
**Purpose**: Main content wrapper
**File**: `courses/static/courses/css/layout.css`
**Used In**: All primary content pages

#### `.l-main__inner`
**Purpose**: Inner content grid
**Definition**:
```css
.l-main__inner {
    max-width: var(--main-max);
    display: grid;
    gap: var(--space-5);
    justify-items: stretch;
}
```

---

## 4. TOPBAR/HEADER COMPONENT CLASSES

### `.topbar` System

#### `.topbar`
**Purpose**: Sticky top navigation bar
**File**: `courses/static/courses/css/layout.css`
**Definition**:
```css
.topbar {
    position: sticky;
    top: 0;
    z-index: 1100;
    background: linear-gradient(120deg, var(--color-primary) 0%, #2f9e63 100%);
    border-bottom: 1px solid color-mix(in srgb, var(--color-primary) 70%, black);
}
```
**Used In**: All app base templates
**Modules**: Courses, Account, Assistant, Students

#### `.topbar__inner`
**Purpose**: Container for topbar content
**Definition**:
```css
.topbar__inner {
    min-height: var(--topbar-height);
    margin: 0 auto;
    padding: var(--space-3) 0;
    max-width: 1600px;
    display: grid;
    grid-template-columns: auto minmax(280px, 500px) 1fr auto;
    gap: var(--space-3);
    align-items: center;
}
```

#### `.topbar__brand-wrap`
**Purpose**: Brand/logo container
**Definition**:
```css
.topbar__brand-wrap {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
}
```
**Child Elements**: `.brand-icon`, `.brand-text`, `.brand-divider`, `.brand-secondary`

#### `.topbar__actions`
**Purpose**: Right-side action buttons/dropdowns
**Definition**:
```css
.topbar__actions {
    display: inline-flex;
    gap: var(--space-2);
    align-items: center;
    margin-left: auto;
    flex-shrink: 0;
}
```
**Used In**: Theme toggle, user menu, notifications

#### `.topbar__drawer`
**Purpose**: Container for search, countdown, and actions
**Definition**:
```css
.topbar__drawer {
    grid-column: 2 / 4;
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: nowrap;
    min-width: 0;
}
```

#### `.skip-link`
**Purpose**: Accessibility skip-to-content link
**File**: `courses/static/courses/css/layout.css`
**Definition**:
```css
.skip-link {
    position: absolute;
    left: var(--space-4);
    top: -120px;
    z-index: 2000;
    background: var(--color-accent);
    color: #fff;
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-sm);
    transition: top 0.12s ease-in-out;
}
.skip-link:focus-visible {
    top: var(--space-4);
}
```
**Used In**: All base templates

---

## 5. SEARCH COMPONENT CLASSES

### `.c-search` System

**File**: `courses/static/courses/css/unified.css`

#### `.c-search`
**Purpose**: Search input container
**Definition**:
```css
.c-search {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    width: 100%;
    position: relative;
    max-width: 500px;
}
```
**Used In**:
- Topbar search
- Course search filters
- Learning insights search

#### `.c-search__icon`
**Purpose**: Search icon positioning
**Definition**:
```css
.c-search__icon {
    position: absolute;
    left: var(--space-3);
    width: 18px;
    height: 18px;
    pointer-events: none;
    color: color-mix(in srgb, var(--color-text) 60%, white);
}
```

#### `.c-search__input`
**Purpose**: Search input field styling
**Definition**:
```css
.c-search__input {
    width: 100%;
    min-height: 44px;
    border-radius: 999px;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    padding: 0 var(--space-4);
    padding-left: 2.5rem;
    font-size: var(--fs-0);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65),
                0 6px 20px rgba(var(--color-shadow), 0.04);
}
```

**Topbar Variant**:
```css
.c-search.topbar__search {
    gap: 0;
    border-radius: 999px;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
}
```
**Used In**:
- Topbar (all apps)
- Course search
- Learning insights

---

## 6. CARD COMPONENT CLASSES

### `.c-card` System

**File**: `courses/static/courses/css/unified.css`

#### `.c-card`
**Purpose**: Generic card/panel component
**Definition**:
```css
.c-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: clamp(1rem, 0.85rem + 0.55vw, 1.35rem);
    box-shadow: 0 18px 48px rgba(var(--color-shadow), 0.08);
    display: grid;
    gap: var(--space-3);
}
```
**Used In**:
- Course cards in catalog
- Assignment cards
- Goal/insight cards
- Learning insights dashboard
- Account settings panels

#### `.c-card__title`
**Purpose**: Card title styling
**Definition**:
```css
.c-card__title {
    font-size: clamp(1.05rem, 0.95rem + 0.45vw, 1.35rem);
    font-weight: 600;
    letter-spacing: -0.02em;
}
```

#### `.c-card__meta`
**Purpose**: Card metadata (description, dates)
**Definition**:
```css
.c-card__meta {
    color: var(--color-text-muted);
    font-size: var(--fs-0);
    line-height: 1.55;
}
```

#### `.c-card__actions`
**Purpose**: Card action buttons container
**Definition**:
```css
.c-card__actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
}
```

#### `.c-card__meta--flush`
**Purpose**: Remove default margin from meta
**Definition**:
```css
.c-card__meta--flush {
    margin: 0;
}
```

---

## 7. BUTTON COMPONENT CLASSES

### `.c-btn` System

**File**: `courses/static/courses/css/unified.css`

#### `.c-btn`
**Purpose**: Primary button styling
**Definition**:
```css
.c-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: 0.625rem 1rem;
    font-size: var(--fs-0);
    font-weight: 600;
    letter-spacing: 0.01em;
    min-height: 44px;
    border-radius: 999px;
    border-color: transparent;
    box-shadow: 0 8px 18px rgba(var(--color-shadow), 0.04);
    transition: transform 0.16s ease, box-shadow 0.16s ease,
                background-color 0.16s ease, border-color 0.16s ease,
                color 0.16s ease;
}
```
**Used In**:
- Course enrollment buttons
- Form submission buttons
- Account actions (password reset, logout, etc.)
- Goal creation/editing
- Search filters

**Modifiers**:
- `.c-btn--ghost` - Transparent background variant
- `.c-btn--primary` - Primary color variant
- `.c-btn--secondary` - Secondary color variant

---

## 8. NAVIGATION COMPONENT CLASSES

### `.c-nav` System

**File**: `courses/static/courses/css/unified.css`

#### `.c-nav`
**Purpose**: Vertical navigation list
**Definition**:
```css
.c-nav {
    display: grid;
    gap: 0.45rem;
}
```
**Used In**:
- Sidebar course modules
- Account settings menu
- Learning insights navigation

#### `.c-nav__item`
**Purpose**: Navigation item styling
**Definition**:
```css
.c-nav__item {
    min-height: 44px;
    border-radius: 1rem;
    border: 1px solid transparent;
    padding: 0.8rem 0.95rem;
    display: flex;
    align-items: center;
    color: var(--color-text);
    background: transparent;
    font-weight: 650;
    letter-spacing: -0.01em;
}
.c-nav__item:hover {
    background: var(--color-secondary-surface);
    color: var(--color-text);
    border-color: var(--color-border);
}
```

#### `.c-nav__item.is-active`
**Purpose**: Active navigation state
**Definition**:
```css
.c-nav__item.is-active {
    border-color: var(--color-primary);
    background: linear-gradient(135deg, rgba(15, 118, 110, 0.08), 
                                        rgba(37, 99, 235, 0.06));
    color: var(--color-text);
    box-shadow: 0 10px 24px rgba(var(--color-shadow), 0.07);
}
```

---

## 9. FORM INPUT CLASSES

### Input & Form Styling

**File**: `courses/static/courses/css/unified.css`

#### Common Input Elements
**Selector**: `input:not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="file"]), select, textarea, .c-input`

**Definition**:
```css
input[not specific types],
select,
textarea,
.c-input {
    min-height: 48px;
    border-radius: 0.95rem;
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
}
```
**Used In**:
- Login/registration forms (account)
- Course enrollment forms
- Goal creation forms
- Preference settings

---

## 10. PROGRESS & PROGRESS CARD CLASSES

### `.c-progress` System

**File**: `courses/static/courses/css/unified.css`

#### `.c-progress-card`
**Purpose**: Card wrapper for progress
**Definition**:
```css
.c-progress-card {
    background: linear-gradient(135deg, var(--color-surface) 0%,
                                        var(--color-surface-soft) 100%);
}
```

#### `.c-progress`
**Purpose**: Progress bar container
**Definition**:
```css
.c-progress {
    width: 100%;
    height: 0.8rem;
    border-radius: 999px;
    background: var(--color-border);
    overflow: hidden;
}
```

#### `.c-progress__bar`
**Purpose**: Animated progress indicator
**Definition**:
```css
.c-progress__bar {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--color-primary), 
                                       var(--color-accent));
    transition: width 0.16s ease-in-out;
}
```

#### `.c-progress__text`
**Purpose**: Progress label
**Definition**:
```css
.c-progress__text {
    font-size: var(--fs-0);
    color: var(--color-text-muted);
}
```
**Used In**:
- Course progress display
- Learning goals progress
- Exam preparation tracking

---

## 11. ALERT/MESSAGE CLASSES

### `.c-alert` System

**File**: `courses/static/courses/css/unified.css`

#### `.c-alert`
**Purpose**: Alert/notification box
**Definition**:
```css
.c-alert {
    position: relative;
    padding-right: 42px;
    border: 1px solid var(--color-border);
    border-left: 4px solid transparent;
    border-radius: var(--radius-md);
    background: var(--color-surface);
}
```

**Variants**:
- `.c-alert--info` - Information alert (accent color)
- `.c-alert--warn` - Warning alert (warning color)
- `.c-alert--success` - Success alert (primary color)
- `.c-alert--error` - Error alert (error color)

#### `.c-alert__icon`
**Purpose**: Alert icon styling
**Definition**:
```css
.c-alert__icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    width: 26px;
    height: 26px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 0.95rem;
    background: color-mix(in srgb, var(--color-border) 35%, white);
    color: var(--color-text);
}
```

#### `.c-message-stack`
**Purpose**: Stack of alert messages
**Definition**:
```css
.c-message-stack {
    display: grid;
    gap: 0.75rem;
    margin-bottom: 1rem;
}
```
**Used In**:
- Form error messages
- Success notifications
- System messages

---

## 12. STACK & SPACING CLASSES

### `.c-stack`
**Purpose**: Vertical spacing helper (grid with gaps)
**File**: `courses/static/courses/css/utilities.css`

**Definition**:
```css
.c-stack {
    display: grid;
    gap: var(--space-4);
}
```
**Also in unified.css**:
```css
.c-stack {
    border-radius: var(--radius-lg);
}
```
**Used In**:
- Page containers (all apps)
- Content sections
- Learning insights sections

---

## 13. EXAM COUNTDOWN CLASSES

### `.exam-countdown` System

**File**: `courses/static/courses/css/unified.css`

#### `.exam-countdown`
**Purpose**: Exam timer display in topbar
**Definition**:
```css
.exam-countdown {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.4rem 0.6rem;
    font-size: var(--fs-0);
    white-space: nowrap;
    border-radius: 0.75rem;
    background: rgba(42, 157, 102, 0.12);
    border: 1px solid rgba(42, 157, 102, 0.25);
    transition: all 0.3s ease;
}
```

**States**:
- `.countdown--critical` - Under 5 minutes (red)
- `.countdown--warning` - Under 15 minutes (orange)
- `.countdown--caution` - Under 30 minutes (amber)

#### `.exam-countdown__timer`
**Purpose**: Monospace timer display
**Definition**:
```css
.exam-countdown__timer {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-weight: 700;
    font-size: 0.75rem;
    letter-spacing: 0.02em;
    white-space: nowrap;
}
```
**Used In**:
- Course detail pages (during exams)
- Test pages

---

## 14. MOTTO COMPONENT CLASSES

### `.motto-` System (Daily Quotes/Mottos)

**File**: `courses/static/courses/css/utilities.css`

#### `.motto-header`
**Purpose**: Container for motto with refresh button
**Definition**:
```css
.motto-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
}
```

#### `.motto-text`
**Purpose**: Main motto/quote text
**Definition**:
```css
.motto-text {
    color: var(--color-text);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.45;
}
```

#### `.motto-refresh`
**Purpose**: Refresh button for new motto
**Definition**:
```css
.motto-refresh {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: 2.5rem;
    block-size: 2.5rem;
    min-width: 2.5rem;
    min-height: 2.5rem;
    padding: 0;
    font-size: 0.7rem;
    border-radius: 50%;
    line-height: 0;
    flex: 0 0 auto;
}
```

#### `.motto-context`, `.motto-source`, `.motto-link`
**Purpose**: Supporting text styling
**Definition**:
```css
.motto-context {
    color: var(--color-text-muted);
    line-height: 1.55;
}
.motto-source {
    color: var(--color-text-muted);
    font-weight: 500;
}
.motto-link {
    color: var(--color-primary);
    font-weight: 600;
    text-decoration: underline;
}
```
**Used In**:
- Learning dashboard (top section)
- Student home page

---

## 15. PAGE & PAGE-HEADING CLASSES

### `.page` System

**File**: `courses/static/courses/css/pages.css`

#### `.page`
**Purpose**: Main page container
**Definition**:
```css
.page {
    display: grid;
    gap: var(--space-5);
}
```
**Used In**:
- All primary content pages
- API dashboard
- Search results

#### `.page-heading`
**Purpose**: Page title section
**Definition**:
```css
.page-heading {
    display: grid;
    gap: var(--space-2);
}
```

#### `.page-title`
**Purpose**: Large page title
**Definition**:
```css
.page-title {
    font-size: clamp(var(--fs-3), 2.2vw, var(--fs-5));
    font-weight: 700;
}
```

#### `.page-subtitle`
**Purpose**: Secondary text under title
**Definition**:
```css
.page-subtitle {
    color: var(--color-text-muted);
    font-size: var(--fs-0);
}
```
**Used In**:
- Course catalog pages
- Search results
- Account settings
- Learning insights overview

---

## 16. ASSISTANT-SPECIFIC CLASSES

### Assistant Sidebar Classes

**File**: `assistant/static/assistant/css/assistant.css`

#### `.app-body.has-assistant`
**Purpose**: Body state when assistant is active
**Definition**:
```css
.app-body.has-assistant {
    --assistant-content-offset: var(--assistant-sidebar-width);
}
```

#### `.app-body.has-assistant.assistant-sidebar-open`
**Purpose**: Assistant sidebar expanded state
**Definition**:
```css
.app-body.has-assistant.assistant-sidebar-open {
    --rail-left-current: var(--rail-left-compact);
    --workspace-modules-min-current: var(--course-modules-min-compact);
    --workspace-modules-max-current: var(--course-modules-max-compact);
    --rail-right: var(--assistant-content-offset);
    --util-width: var(--assistant-content-offset);
}
```

#### `.app-body.has-assistant.assistant-hidden`
**Purpose**: Assistant sidebar hidden state
**Definition**:
```css
.app-body.has-assistant.assistant-hidden {
    --util-width: 0px;
}
```

#### `.c-ai-panel`
**Purpose**: AI assistant panel container
**Definition**:
```css
.c-ai-panel {
    min-height: min(74vh, 920px);
}
```
**Used In**:
- Course pages with AI assistant enabled
- All course detail pages

---

## 17. ACCOUNT-SPECIFIC CLASSES

### File Locations
- Account Auth: `account/static/account/css/account-auth.css`
- Account Menu: `account/static/account/css/account-menu.css`
- OTP Email: `account/static/account/css/otp_email.css`

**Used In**:
- Login/registration pages
- Email verification pages
- Password reset pages
- User profile dropdown menu

---

## 18. THEME TOGGLE CLASS

### `#theme-toggle-link`
**Purpose**: Theme toggle button styling
**File**: `courses/static/courses/css/unified.css`

**Definition**:
```css
#theme-toggle-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.theme-icon svg {
    display: block;
}
```
**Used In**: Topbar actions (all apps)

---

## 19. SCROLLBAR STYLING

### Browser Scrollbar Customization

**File**: `courses/static/courses/css/pages.css`

**Definition**:
```css
html,
body {
    scrollbar-color: #54586d #282a36;
    scrollbar-width: thin;
}
html::-webkit-scrollbar,
body::-webkit-scrollbar {
    width: 9px;
}
html::-webkit-scrollbar-track,
body::-webkit-scrollbar-track {
    background: #282a36;
}
html::-webkit-scrollbar-thumb,
body::-webkit-scrollbar-thumb {
    background: #54586d;
    border-radius: 999px;
}
```
**Applied to**: All pages

---

## 20. RESET STYLES

### Global Reset

**File**: `courses/static/courses/css/reset.css`

**Key Resets**:
- Box-sizing: `border-box` on all elements
- Margin/padding reset for `html`, `body`
- List styling removed (`li { list-style: none }`)
- Heading margin reset
- Focus ring: `outline: 3px solid var(--color-focus-ring)`
- Image/media max-width: `100%`
- Font inheritance for form elements

---

## CSS DEPENDENCY MAP

```
┌─ tokens.css (Design System Variables)
│  └─ reset.css (Global element reset)
│  └─ layout.css (Grid layout system)
│  │  ├─ .app-body
│  │  ├─ .l-shell