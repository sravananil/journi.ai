---
name: Voyex AI
colors:
  surface: '#fbf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fbf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f2'
  surface-container: '#f0eded'
  surface-container-high: '#eae8e7'
  surface-container-highest: '#e4e2e1'
  on-surface: '#1b1c1c'
  on-surface-variant: '#5b4039'
  inverse-surface: '#303030'
  inverse-on-surface: '#f3f0f0'
  outline: '#907067'
  outline-variant: '#e4beb4'
  surface-tint: '#b02f00'
  primary: '#b02f00'
  on-primary: '#ffffff'
  primary-container: '#ff5722'
  on-primary-container: '#541200'
  inverse-primary: '#ffb5a0'
  secondary: '#495a9f'
  on-secondary: '#ffffff'
  secondary-container: '#a2b2fe'
  on-secondary-container: '#314286'
  tertiary: '#00628c'
  on-tertiary: '#ffffff'
  tertiary-container: '#007caf'
  on-tertiary-container: '#fcfcff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbd1'
  primary-fixed-dim: '#ffb5a0'
  on-primary-fixed: '#3b0900'
  on-primary-fixed-variant: '#862200'
  secondary-fixed: '#dde1ff'
  secondary-fixed-dim: '#b8c4ff'
  on-secondary-fixed: '#001454'
  on-secondary-fixed-variant: '#314286'
  tertiary-fixed: '#c8e6ff'
  tertiary-fixed-dim: '#86cfff'
  on-tertiary-fixed: '#001e2e'
  on-tertiary-fixed-variant: '#004c6d'
  background: '#fbf9f8'
  on-background: '#1b1c1c'
  surface-variant: '#e4e2e1'
  obsidian: '#333333'
  surface-gray: '#EEEEEE'
  electric-orange: '#FF5722'
  deep-indigo: '#334488'
typography:
  headline-xl:
    fontFamily: Outfit
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Outfit
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  headline-sm:
    fontFamily: Outfit
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  margin: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes a premium, modern SaaS aesthetic tailored for an AI-powered travel itinerary planner. The brand personality is intelligent, efficient, inspiring, and contemporary. It bridges the gap between sophisticated travel curation and cutting-edge machine learning.

The UI evokes a sense of effortless discovery and high-performance utility, combining crisp minimalism with vibrant, energetic accents. We employ a refined Glassmorphism approach to convey layering and intelligent spatial organization, using translucent surfaces and backdrop filters to give a sense of depth and contextual focus.

## Colors

The color palette is built on high-contrast foundations of crisp white backgrounds and deep obsidian black text, accented by a vibrant energetic orange for primary actions, active states, and critical highlights. Soft gray surfaces provide subtle background differentiation for structural components, while deep indigo serves as a sophisticated secondary anchor for data visualizations and brand moments. Glassmorphism layers utilize translucent whites with refined border strokes to maintain supreme legibility.

## Typography

Typography balances geometric modernity with pristine legibility. **Outfit** is deployed for headlines to impart a visionary, architectural quality, while **Inter** anchors the system for body copy and UI labels, ensuring data density and readability across complex itinerary grids. Font sizes above 32px automatically step down on mobile viewports to preserve layout integrity.

## Layout & Spacing

A fluid grid system governs the layout, adapting dynamically from a single-column view on mobile devices to a structured 12-column workspace on desktop. Spacing follows an 8px base rhythm, ensuring consistent optical alignment across densely populated itinerary builder views and expansive map interfaces. Margins scale down gracefully on mobile form factors to maximize interactive real estate.

## Elevation & Depth

Depth is communicated primarily through a sophisticated **Glassmorphism** model combined with ambient, low-opacity shadows. Floating panels, modals, and itinerary cards utilize semi-transparent white fills (`rgba(255, 255, 255, 0.75)`) paired with a `12px` backdrop blur and delicate 1px borders (`rgba(255, 255, 255, 0.4)`). This creates a frosted, layered architectural depth that keeps background map data and imagery subtly visible.

## Shapes

The design system uses a roundedness level of `2` (Rounded), establishing a friendly yet precise architectural language. Standard interactive elements and cards feature a `0.5rem` radius, while large containers and modal surfaces scale up to `1rem` (`rounded-lg`) and `1.5rem` (`rounded-xl`). This softens the high-contrast obsidian and white palette, making dense data layouts feel approachable and tactile.

## Components

### Buttons
Primary actions utilize the vibrant energetic orange with crisp typography, subtle scale-up micro-interactions on hover, and clear focus rings. Secondary actions employ ghost styles or soft gray surfaces with obsidian text.

### Chips & Tags
Compact elements used for travel tags, categories, and AI prompts. Styled with soft gray backgrounds or translucent glass fills, featuring label-sm typography and rounded-pill geometry.

### Input Fields
Clean text inputs featuring a soft gray background, subtle borders, and obsidian text. Focus states transition immediately to the primary energetic orange border with an ambient glow.

### Cards
Built using glassmorphism principles: translucent surfaces, backdrop blur, soft internal padding, and delicate borders. Ideal for surfacing day-by-day itinerary segments, destination highlights, and AI recommendations.

### Checkboxes & Radio Buttons
Minimalist geometry utilizing obsidian strokes for unselected states and solid energetic orange fills for selected states, paired with smooth transition animations.

### Lists
Clean, structured data rows with generous padding to prevent cognitive overload. Optimized for itinerary timelines, featuring small icon anchors and clear typographic hierarchy.