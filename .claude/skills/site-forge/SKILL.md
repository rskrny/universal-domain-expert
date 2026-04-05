---
name: site-forge
description: "Generate premium agency-quality websites from minimal business info. Creates brand brief, Next.js 14 site with designer-grade animations and components, AI-generated assets, and live QA verification. TRIGGER when: user asks to build a website, create a site, generate a landing page, or make a web presence for a business. DO NOT TRIGGER when: user is editing an existing codebase, fixing bugs, or doing general frontend work."
user_invocable: true
---

# Site Forge -- Premium Website Generator

Generate agency-quality websites from minimal business info. Three phases:
brand brief, build, then assets and QA. Every site ships with designer-grade
animations, premium typography, and polished components.

## Inputs

Ask the user for these. Only business name and type are required.

| Field | Required | Example |
|-------|----------|---------|
| Business name | Yes | "Kona Coffee House" |
| Business type | Yes | "specialty coffee shop" |
| Location | No | "Kailua-Kona, Hawaii" |
| Services/products | No | "pour-over, espresso, pastries, beans" |
| Aesthetic direction | No | "warm, earthy, modern" |
| Existing brand colors | No | "#2C1810, #D4A574" |
| Google Maps / website URL | No | Used for research |

If the user provides a Google Maps link or website URL, research the business
first. Pull the name, type, location, services, photos, reviews, and any
existing brand elements before proceeding.

---

## Phase 1: Brand Brief

Generate a structured brand brief. This drives every design decision in Phase 2.

### 1A. Brand Identity

Produce all of the following:

**Brand Personality:** 3-5 adjectives that define the brand voice.
Example: "warm, artisanal, confident, approachable"

**Color Palette:** Generate exactly 6 colors with hex codes:
- Primary (dominant brand color)
- Secondary (accent/complement)
- Background (warm off-white, never #ffffff. Use #fafaf8, #f5f5f0, or #e8e6e1)
- Surface (cards, elevated elements. Slightly different from background)
- Text primary (near-black, never #000000. Use #1a1a1a, #2d2d2d, or #333333)
- Text secondary (muted, for captions and metadata)

**Rule:** Never use default CSS color names. Every color is a custom hex value.

**Typography Pairing:** Select one serif + one sans-serif:

Serif options (for headings):
- Playfair Display
- DM Serif Display
- Lora
- Cormorant Garamond
- Libre Baskerville

Sans-serif options (for body):
- DM Sans
- Inter
- Outfit
- Plus Jakarta Sans

### 1B. Content Plan

For each section, generate the actual copy:

1. **Navbar:** Logo text, 4-5 nav links, CTA button text
2. **Hero:** Uppercase label (2-3 words), headline (5-8 words, serif), subtext (1-2 sentences), CTA button text
3. **Trust Badges:** 3-4 stats or credentials (e.g., "500+ Happy Customers", "Est. 2018")
4. **Features / About (Bento Grid):** 4-6 feature blocks with title + short description
5. **Products / Services Grid:** 8-12 items, each with name, short description, price or label, category tag
6. **Testimonials:** 9 reviews with reviewer name, role/location, star rating, review text (2-3 sentences each)
7. **CTA Banner:** Headline, subtext, button text
8. **Newsletter:** Headline, subtext, placeholder text, button text
9. **Footer:** Business name, tagline, 3 column link groups, social links, copyright

### 1C. Asset Brief

List the images needed:
- Hero background (1 image, describe the scene)
- Feature/about images (2-4 images, describe each)
- Product/service images (8-12 images, describe each)
- Testimonial avatars (optional, can use initials instead)

Present the full brand brief to the user. Get approval before Phase 2.

---

## Phase 2: Build the Site

### Technical Stack

```
Framework:    Next.js 14 (App Router)
Language:     TypeScript
Styling:      Tailwind CSS
Icons:        Lucide React
Animations:   Pure CSS + IntersectionObserver ONLY
Images:       Generated via MiniMax or Unsplash URLs
Font loading: next/font/google
```

**Hard rules:**
- NO Framer Motion
- NO GSAP
- NO AOS
- NO external animation libraries
- Components in `/components/{brand-name-kebab}/`
- Each section is its own component file
- Shared layout/state via React Context if needed
- Mobile-first responsive
- Semantic HTML with aria-labels on interactive elements

### Project Scaffold

Create the project with `npx create-next-app@latest {project-name} --typescript --tailwind --app --src-dir --no-eslint` or scaffold manually if faster.

Install only: `lucide-react`

Configure `tailwind.config.ts` with the brand colors, fonts, and extended theme values from the brief.

Configure `next.config.js` for remote image domains if using external URLs.

Load Google Fonts via `next/font/google` in the root layout.

### Design System Specifications

Apply these specs to every component. These are non-negotiable.

#### Colors
```
Background:     var(--background) from brief, warm off-white
Surface:        var(--surface) slightly elevated
Text:           var(--foreground) near-black
Accent:         var(--primary) brand primary
```
Never use `bg-white`, `bg-black`, `text-black`, `text-white`, `bg-gray-*`.
Always use the custom palette from the brief.

#### Typography Scale
```
Hero headline:       text-7xl (desktop) / text-5xl (mobile), serif font, font-bold
Section headings:    text-4xl / text-3xl, serif font
Section labels:      text-sm uppercase tracking-[0.2em], text-secondary, font-medium
Body text:           text-base / text-lg, sans-serif font
Card titles:         text-xl font-semibold
Captions:            text-sm text-secondary
```

#### Corners
```
Cards, images, buttons, inputs:  rounded-3xl (border-radius: 24px)
Small pills, badges:             rounded-full
Never use rounded-md or rounded-lg. Everything is either rounded-3xl or rounded-full.
```

#### Spacing
```
Between sections:    py-24 (96px vertical padding)
Section inner:       max-w-7xl mx-auto px-6
Card padding:        p-6 or p-8
Grid gap:            gap-4 or gap-6
```

#### Shadows
```
Card shadow:         shadow-[0_2px_8px_rgba(0,0,0,0.04),0_8px_32px_rgba(0,0,0,0.06)]
Hover shadow:        shadow-[0_4px_16px_rgba(0,0,0,0.08),0_16px_48px_rgba(0,0,0,0.1)]
Navbar shadow:       shadow-[0_2px_16px_rgba(0,0,0,0.06)]
```
Never use Tailwind's default `shadow-md` or `shadow-lg`. Always use custom rgba shadows.

### Animation System

#### Scroll Reveal (IntersectionObserver)

Create a `useScrollReveal` hook or a `<ScrollReveal>` wrapper component:

```
Initial state:     opacity-0, scale-95, translateY(20px)
Revealed state:    opacity-100, scale-100, translateY(0)
Duration:          700ms
Easing:            ease-out
Trigger:           IntersectionObserver, threshold 0.1
Once:              true (do not re-hide on scroll up)
```

Apply to: every card, every section, every grid item.
Stagger grid items by adding `transition-delay: index * 100ms`.

#### Text Blur-In (Section Headings)

```
Initial:           opacity-0, filter: blur(8px), translateY(10px)
Final:             opacity-1, filter: blur(0), translateY(0)
Duration:          600ms ease-out
Stagger:
  - Label:         delay 200ms
  - Headline:      delay 400ms
  - Subtext:       delay 600ms
```

Apply to: every section heading group (label + headline + subtext).

#### Hover Micro-Interactions

```
Cards:             transform: scale(1.02), transition 300ms ease
Buttons:           translateX arrows, slight brightness shift
Images:            scale(1.05) with overflow-hidden on container
Nav links:         underline slide-in from left
```

#### Testimonial Auto-Scroll

```
CSS keyframes:
  @keyframes scroll-down {
    0%   { transform: translateY(0); }
    100% { transform: translateY(-50%); }
  }
  @keyframes scroll-up {
    0%   { transform: translateY(-50%); }
    100% { transform: translateY(0); }
  }

Duration:          30s infinite linear
On hover:          animation-duration: 60s (slow down)
Column 1 & 3:      scroll-down
Column 2:           scroll-up
Container:          h-[600px] overflow-hidden
Content:            duplicate the testimonial list (render twice) so scroll loops seamlessly
```

### Component Blueprints

Build each as a separate file in `/components/{brand-name}/`.

#### Navbar
```
Position:          fixed top-0 left-0 right-0 z-50
Container:         mx-4 mt-4 (floating with margin from edges)
Height:            h-[68px]
Background:        backdrop-blur-md bg-[rgba(255,255,255,0.4)]
Border:            border border-[rgba(255,255,255,0.32)]
Corners:           rounded-full
Shadow:            navbar shadow spec
Layout:            flex items-center justify-between px-6
Logo:              text-xl font-bold serif
Links:             hidden md:flex gap-8 text-sm
CTA:               rounded-full px-6 py-2 bg-primary text-white
Mobile:            hamburger icon, slide-out drawer
```

#### Hero Section
```
Height:            min-h-screen
Layout:            flex items-center justify-center relative
Background:        full-bleed image or video, object-cover
Overlay:           absolute inset-0 bg-gradient-to-t from-background via-background/50 to-transparent
                   Gradient covers bottom 60% of hero
Content:           relative z-10, text-center or text-left
Structure:
  1. Uppercase label (text-sm tracking-[0.2em] text-secondary)
  2. Headline (text-7xl md:text-5xl serif font-bold, max-w-4xl)
  3. Subtext (text-lg text-secondary max-w-2xl)
  4. CTA button (rounded-full px-8 py-4 bg-primary text-white text-lg)
All text gets blur-in animation with stagger.
```

#### Trust Badges
```
Layout:            flex flex-wrap justify-center gap-8 py-12
                   border-y border-border/10
Each badge:        flex flex-col items-center
  Number:          text-3xl font-bold serif
  Label:           text-sm text-secondary
```

#### Feature Section (Bento Grid)
```
Desktop grid:      grid-cols-4 grid-rows-[300px_300px] gap-4
Mobile:            grid-cols-1 or grid-cols-2

Block types:
  Large (1 block):   col-span-2 row-span-2
                     Background image/video
                     White overlay card at bottom: bg-white/90 backdrop-blur p-6 rounded-2xl
                     Contains: icon, title, description
  Standard (4):      col-span-1 row-span-1
                     bg-surface rounded-3xl p-6
                     Contains: icon, title, description
                     Hover: scale(1.02) + shadow increase

Each block gets scroll-reveal with stagger.
```

#### Products / Services Grid
```
Filter bar:
  Layout:          flex gap-2 overflow-x-auto pb-4
  Each pill:       px-4 py-2 rounded-full text-sm cursor-pointer
  Active pill:     bg-primary text-white
  Inactive:        bg-surface text-secondary
  Animation:       sliding background div (absolute positioned, transitions left+width)
                   Use React state to track active filter position

Grid:
  Desktop:         grid-cols-4 gap-4
  Tablet:          grid-cols-2
  Mobile:          grid-cols-1

Each card:
  Container:       rounded-3xl overflow-hidden bg-surface group cursor-pointer
  Image:           aspect-square object-cover
  Badge:           absolute top-4 left-4 rounded-full bg-white/90 backdrop-blur px-3 py-1 text-xs
  Body:            p-4
    Title:         text-lg font-semibold
    Description:   text-sm text-secondary line-clamp-2
    Price/Label:   text-primary font-bold
  Hover:           image scale(1.05), shadow increase
  Scroll-reveal with stagger per card
```

#### Testimonials
```
Desktop:           grid-cols-3 gap-4, h-[600px] overflow-hidden
Mobile:            single column, horizontal scroll or stacked

Each testimonial card:
  Container:       rounded-3xl bg-surface p-6 mb-4
  Stars:           flex gap-1, filled star icons in primary color
  Quote:           text-base mt-3
  Author:          flex items-center gap-3 mt-4
    Avatar:        w-10 h-10 rounded-full (image or initials on colored bg)
    Name:          text-sm font-semibold
    Role:          text-xs text-secondary

Auto-scroll:
  Column wrapper:  flex flex-col animation (see Animation System above)
  Content:         render testimonials twice for seamless loop
  Col 1 & 3:       scroll-down direction
  Col 2:           scroll-up direction
  Hover on section: animation slows to 60s
```

#### CTA Banner
```
Container:         rounded-3xl bg-primary text-white p-16 text-center
Headline:          text-4xl serif font-bold
Subtext:           text-lg opacity-80 mt-4
Button:            rounded-full px-8 py-4 bg-white text-primary font-semibold mt-8
                   Hover: scale(1.02)
```

#### Newsletter
```
Container:         py-24 text-center
Headline:          text-3xl serif
Subtext:           text-secondary mt-2
Form:              flex mt-8 max-w-md mx-auto
  Input:           flex-1 rounded-full px-6 py-3 bg-surface border-none
  Button:          rounded-full px-8 py-3 bg-primary text-white ml-2
```

#### Footer
```
Container:         pt-24 pb-12 relative overflow-hidden
Watermark:         absolute bottom-0 left-1/2 -translate-x-1/2
                   text-[200px] md:text-[400px] font-bold serif
                   opacity-[0.03] select-none pointer-events-none
                   whitespace-nowrap
Content (on top):  relative z-10
  Top row:         grid grid-cols-4 gap-8 (logo + 3 link groups)
  Bottom row:      flex justify-between items-center pt-8 border-t border-border/10
    Copyright:     text-sm text-secondary
    Social icons:  flex gap-4
```

---

## Phase 3: Assets and QA

### 3A. Generate Images

Use the MiniMax `text_to_image` tool to generate images for:
- Hero background (aspect ratio 16:9 or 21:9)
- Feature/about section images (1:1 or 4:3)
- Product/service images (1:1, consistent style across all)

Prompt structure for MiniMax:
```
"Professional {business type} photography, {specific scene description},
{brand adjectives} aesthetic, warm natural lighting, high-end commercial quality,
editorial style, {color hints from palette}"
```

Save generated images to the project's `/public/images/` directory.
Update component image paths to reference the generated files.

### 3B. Quality Assurance Checklist

Use Claude Preview tools to verify every item. Start the dev server with
`preview_start`, then check:

**Visual Checks (use preview_screenshot + preview_inspect):**
- [ ] Navbar floats with frosted glass effect (backdrop-blur visible)
- [ ] Hero headline is immediately legible and large (text-7xl on desktop)
- [ ] Background has no default white (#fff) or black (#000) anywhere
- [ ] All corners are rounded-3xl or rounded-full (no sharp corners)
- [ ] Custom shadows render (no default Tailwind shadow classes)
- [ ] Typography pairing is correct (serif headings, sans-serif body)
- [ ] Color palette matches the brief (check 3+ elements with preview_inspect)

**Animation Checks (use preview_eval + preview_snapshot):**
- [ ] Sections fade and scale into view on scroll
- [ ] Section headings use blur-in animation with stagger
- [ ] Cards scale on hover (1.02)
- [ ] Product filter pills animate with sliding background
- [ ] Testimonials auto-scroll in alternating directions

**Responsive Checks (use preview_resize):**
- [ ] Mobile: hero text is text-5xl, readable
- [ ] Mobile: navbar shows hamburger menu
- [ ] Mobile: grids collapse to 1-2 columns
- [ ] Mobile: testimonials stack or scroll horizontally
- [ ] Tablet: intermediate layout works

**Content Checks (use preview_snapshot):**
- [ ] CTA button appears at least 3 times (hero, CTA banner, navbar)
- [ ] All 9 testimonials render
- [ ] Product/service grid shows all items
- [ ] Footer watermark is visible but subtle
- [ ] No placeholder text remaining ("Lorem ipsum", "TODO", etc.)

**Console Checks (use preview_console_logs level=error):**
- [ ] No JavaScript errors
- [ ] No missing image warnings
- [ ] No hydration mismatches

### 3C. Fix and Re-verify

For any failed check:
1. Read the source component file
2. Edit the source to fix the issue
3. Wait for HMR or reload via `preview_eval("window.location.reload()")`
4. Re-run the failed check
5. Continue until all checks pass

### 3D. Deliver

When all checks pass:
1. Take a final `preview_screenshot` and show the user
2. List what was built (component count, image count, section count)
3. Offer next steps: deploy to Vercel, add more pages, customize further

---

## Output Format

After completing all three phases, present a summary:

```
SITE FORGE COMPLETE

Business:      {name}
Sections:      {count} sections across {page count} page(s)
Components:    {count} component files
Images:        {count} generated ({count} AI + {count} placeholder)
QA Status:     {pass count}/{total count} checks passed

Preview:       {dev server URL}
Project:       {project directory path}
```
