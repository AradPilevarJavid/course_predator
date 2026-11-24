# SlideFlare Responsiveness Report

**Scope:** how the app avoids breaking when it moves between a 15.6" laptop and a 27" monitor.
**Question answered:** what makes the deck resolution-independent, and where that guarantee stops.

**Verdict:** SlideFlare is not responsive in the CSS-media-query sense. It is **resolution-independent**: every slide is laid out once on a fixed 1280×720 canvas and then uniformly scaled to the viewport, with a single deck-wide shrink factor preventing vertical overflow. That is what keeps it from "failing" across displays. The guarantee is geometric, not universal — it covers vertical overflow and cross-monitor layout consistency, but not legibility, horizontal overflow from user content, very short windows, or very long decks. Those limits are listed in [§7](#7-where-the-guarantee-stops).

---

## 1. The design model

Instead of reflowing at breakpoints, the app treats the slide as a fixed 16:9 canvas that is scaled like a projector image.

`src/routes/view-slides/shared.svelte.ts:6`

```ts
export const DESIGN_W = 1280;
export const DESIGN_H = 720;
export const VIEWPORT_PADDING = 24;
```

Three properties follow from this choice:

1. **Line breaks never change with monitor size.** Text is always laid out in a 1280 px-wide box (1088 px after `px-24`), so the same words wrap at the same places on a laptop and a 27" screen.
2. **Only one dimension is responsive.** The window width drives the scale; the window height is only an overflow guard.
3. **Every slide shares one scale.** A single shrink factor is derived from the tallest slide, so the deck never has text at two different sizes.

---

## 2. The scaling formula

The live deck computes two values from the window:

`src/routes/view-slides/+page.svelte:42-50`

```ts
let winW = $state(... window.innerWidth  ...);
let winH = $state(... window.innerHeight ...);

let scale     = $derived(shared.printMode ? 1
              : (winW - 2 * VIEWPORT_PADDING) / DESIGN_W);
let maxHeight = $derived(shared.printMode ? DESIGN_H
              : winH - 2 * VIEWPORT_PADDING);
```

Then each slide reports its **natural** content height at design width, and the deck derives one fit factor:

`src/routes/view-slides/+page.svelte:55-76`

```ts
let heights = $state<Record<number, number>>({});

let fitScale = $derived.by(() => {
  let min = 1;
  for (const h of Object.values(heights)) {
    const scaledHeight = h * scale;
    if (scaledHeight > maxHeight && scaledHeight > 0) {
      min = Math.min(min, maxHeight / scaledHeight);
    }
  }
  return min;
});
```

The factor applied to every slide is:

```
widthScale = (innerWidth - 2 × 24) / 1280
fitScale   = min(1, min over slides of (innerHeight - 2 × 24) / (naturalHeight × widthScale))
finalScale = widthScale × fitScale
```

`fitScale` can only shrink (`min` starts at `1`). It never enlarges a short slide to fill height, so slides stay proportional to the width and are vertically centred.

### Why one factor for the whole deck

`src/routes/view-slides/+page.svelte:393-400`

```svelte
<Slide
  ...
  scale={scale * fitScale}
  onMeasure={(h) => reportHeight(index, h)}
/>
```

If each slide shrank independently, a dense slide would render smaller than its neighbours and the deck would visibly change text size while presenting. Taking the worst case across the deck makes one verbose slide reduce the size of all of them — a deliberate trade: **uniform typography over maximum size**.

---

## 3. What a slide actually is

`src/routes/view-slides/Slide.svelte:25-37`

```svelte
<section
  {id}
  class="flex h-screen w-full items-center justify-center overflow-hidden {bgColor}"
  data-title={title}
>
  <div
    class="flex shrink-0 items-center justify-center px-24"
    style="width: {DESIGN_W}px; transform: scale({scale}); transform-origin: center center;"
  >
    <article bind:clientHeight={contentHeight} class="prose prose-xl prose-invert {textColor}">
      {@html content}
    </article>
  </div>
</section>
```

Four details make the geometry work:

- **`h-screen`** makes each slide exactly one viewport tall, so one ArrowDown equals one slide.
- **`overflow-hidden`** is the final clipping boundary. The fit factor keeps content inside it; if a measurement is ever wrong, content is clipped rather than spilling into the next slide.
- **Fixed `width: 1280px` + `shrink-0`** means flexbox can never squeeze the canvas. The untransformed box stays 1280 px wide; the transform only changes what is painted.
- **`transform-origin: center center`** keeps the scaled canvas centred in the viewport, including when the layout box is wider than the window on a small screen.
- **`bind:clientHeight`** on the article reports the *untransformed* natural height. Transforms do not affect layout, so measurement stays independent of the current scale.

This last point is the reason resizing is cheap and stable: resizing changes only `transform`, not layout. The deck does not reflow, re-wrap, or re-measure text when the window moves from 1366 px to 2560 px wide.

---

## 4. How the window and deck stay in sync

| Concern | Mechanism | Location |
| --- | --- | --- |
| Track viewport size | `<svelte:window bind:innerWidth bind:innerHeight>` | `view-slides/+page.svelte:360` |
| Recompute scale | `$derived` from `winW`, `winH` | `view-slides/+page.svelte:49-50` |
| Measure each slide | `bind:clientHeight` → `onMeasure(index, h)` | `Slide.svelte:36`, `+page.svelte:56-58` |
| Invalidate old deck | prune indices ≥ slide count; reset heights on `markdown-updated` | `+page.svelte:61-66`, `:103-110` |
| Keep the viewer on the same slide after resize | `resize` listener calls `scrollIntoView({ behavior: 'instant' })` | `NavBar.svelte:43-45`, `:55` |
| Move the navigation rail with the viewport | `bind:innerHeight` → `navOffsetTop = innerHeight * 0.5 - index * 48` | `NavBar.svelte:49-52`, `:69` |

The resize path is intentionally non-animated. During a drag-resize the active slide is re-anchored instantly on every event, so the viewer never lands between two slides. Keyboard navigation afterwards is smooth (`NavBar.svelte:39`, `+layout.svelte:43-46`).

---

## 5. What the numbers look like on the two machines

The inch measurement is irrelevant; what matters is the **CSS viewport**, which is the physical resolution divided by the OS display-scaling factor. A 15.6" 1080p laptop at 150% scaling has the same CSS viewport as a 1280×720 window.

Base text is `prose-xl` (20 px) multiplied by `widthScale`; `fitScale` may reduce it further for tall slides.

| Window / CSS viewport | Screen context | `widthScale` | Painted slide width | Base text | Height budget |
| --- | --- | --- | --- | --- | --- |
| 800×600 | Tauri default window | 0.588 | 752 px | 11.8 px | 552 px |
| 1366×768 | 15.6" laptop at 100% | 1.030 | 1318 px | 20.6 px | 720 px |
| 1536×864 | 15.6" 1080p at 125% | 1.163 | 1488 px | 23.3 px | 816 px |
| 1920×1080 | 15.6" 1080p at 100% | 1.463 | 1872 px | 29.3 px | 1032 px |
| 2048×1152 | 27" 1440p at 125% | 1.563 | 2000 px | 31.3 px | 1104 px |
| 2560×1440 | 27" 1440p at 100% | 1.963 | 2512 px | 39.3 px | 1392 px |
| 3840×2160 | 4K at 100% | 2.963 | 3792 px | 59.3 px | 2112 px |

The deck is always inset 24 CSS px on each side, so the painted slide width is always `innerWidth - 48`.

### A tall slide on both machines

Take a slide whose natural content height is 900 px at design width:

- **1366×768:** `900 × 1.030 = 927` vs budget `720` → `fitScale = 0.777` → final scale `0.800`; base text `16.0 px`.
- **2560×1440:** `900 × 1.963 = 1766` vs budget `1392` → `fitScale = 0.788` → final scale `1.547`; base text `30.9 px`.

Both fit exactly, neither clips. The laptop version is smaller — that is the cost of uniform scaling. A slide that is dense enough pushes the laptop below comfortable reading size while remaining fine on the 27" screen; see [§7](#7-where-the-guarantee-stops).

---

## 6. Export is deliberately monitor-independent

The print path does **not** inherit the window scale. When a PDF export starts, the frontend sets `printMode`, which forces `scale = 1` and `maxHeight = DESIGN_H` (`view-slides/+page.svelte:49-50`, `export.svelte.ts:174`). The print stylesheet then sizes every slide at exactly 1280×720 CSS px and one page per slide:

`src/app.css:58-93`

```css
@media print {
  @page { size: 960pt 540pt; margin: 0; }

  main > section {
    width: 1280px !important;
    height: 720px !important;
    overflow: hidden !important;
    break-after: page;
  }
}
```

The CLI export also pins its viewport instead of using the monitor:

`src-tauri/src/cli/gui.rs:163-164`

```rust
const EXPORT_WIDTH: f64 = 1280.0;
const EXPORT_HEIGHT: f64 = 720.0;
```

and applies it as a **logical** size (`LogicalSize`, `gui.rs:355`, `:448`, `:513`), so a HiDPI display does not halve the effective viewport. The result is that `slideflare export` produces the same geometry on a laptop and on a 27" monitor.

The self-contained HTML export mirrors the runtime rather than reusing the app's DOM:

`src/lib/export/standalone.ts:237-259`

```js
function applyScale(mode) {
  var printing = mode === 'print';
  var scale = printing ? 1 : (window.innerWidth - 2 * PADDING) / DESIGN_W;
  var maxHeight = printing ? DESIGN_H : window.innerHeight - 2 * PADDING;
  // measure each stage unscaled, then apply the worst-case fit to all
}
```

It measures all slides first, then applies one final scale, and re-runs on `resize`, `load`, `beforeprint`, and `afterprint` (`standalone.ts:322-333`). `#sf-deck` is a block scroll container with `overflow-y: auto` and `scroll-snap-type: y mandatory` (`standalone.ts:67-85`), so the browser export behaves like the app at any window size.

---

## 7. Where the guarantee stops

The scaling system prevents vertical clipping, but it does not make every window or every deck usable. These are the concrete limits, roughly in order of how likely they are to affect a 15.6"/27" setup.

### 7.1 No minimum window size, and no saved geometry

`src-tauri/tauri.conf.json:14-20` declares only `width: 800`, `height: 600` — no `minWidth`, `minHeight`, or persisted window state. The app therefore opens at 800×600 on any monitor (scale ≈ 0.59, base text ≈ 11.8 px) until the user resizes or maximizes. It does not "fail", but it looks very different from a maximized 27" view and gives no hint that the deck is designed to be large.

### 7.2 `overflow: hidden` + `min-h-screen` leaves no fallback at short heights

`src/app.css:6-8` applies `overflow-hidden` to `html`. The home screen (`+page.svelte:104`), error screen (`ErrorScreen.svelte:10`), and both dialogs use `min-h-screen` or `fixed inset-0` without an inner scroll container. At the default 600 px height this is fine; at a manually reduced height, content is clipped with no scrollbar. The tutorial dialog additionally reserves `min-h-[18rem]` (`TutorialOverlay.svelte:100`) and has no `max-height` / `overflow-y: auto`.

### 7.3 The navigation rail has no vertical overflow strategy

`NavBar.svelte:140-141` positions the rail by `innerHeight * 0.5 - index * 48`, and each slide consumes at least 48 px of rail height (`h-12`, `h-18` when active). A 15-slide deck needs ~720 px of rail; a 30-slide deck needs ~1440 px. On a 768 px laptop viewport a long deck will run off the top and bottom of the rail. The multiplier also ignores that the active dot is taller, so the indicator drifts progressively on long decks.

### 7.4 The fit factor protects geometry, not legibility

Because `fitScale` has no lower bound, an extremely dense slide can shrink text arbitrarily. There is no minimum font size, no "this slide will be unreadable" warning, and no automatic slide splitting. On a laptop, a deck that reads well on a 27" monitor can become too small; on the 27" the same deck can look fine. This is the one place where the two-monitor experience genuinely diverges.

### 7.5 Only height is measured; horizontal overflow is clipped

`Slide.svelte:34` fixes the stage at 1280 px, and only `article.clientHeight` is reported. There is no width measurement, no `overflow-x` handling, and user-supplied Tailwind/HTML can introduce elements wider than the 1088 px content box — wide tables, fixed-width grids, `<pre>` with long unbreakable tokens, large MathML, or a `w-[1600px]` div. Those are cut off by `overflow-hidden` rather than scaled. The global rules in `src/app.css` only address `pre`/`code` wrapping, not tables, grids, or arbitrary HTML.

### 7.6 The navigation rail overlays slide content

The rail is a fixed 80 px overlay (`NavBar.svelte:72`), not reserved layout. On a narrow window the slide canvas starts 24 px from the edge and its internal padding is only `24 × scale`; the rail can therefore cover the left edge of wide slide content. On a large monitor the proportion is small and it reads as presentation chrome.

### 7.7 Scale is unclamped at both extremes

`widthScale` is a pure ratio. A 400 px-wide window yields `scale ≈ 0.275` (~5.5 px text); an 8K display yields `scale ≈ 5.9`. Text remains vector-crisp when scaled up, but raster images and video are transform-upscaled from their intrinsic resolution and become soft on large displays. There is no `srcset`, no re-encode at the target size, and no upper bound on the scale.

### 7.8 A few smaller issues

- `Notification.svelte:47` uses `whitespace-nowrap`; a long message extends leftwards across the deck instead of wrapping.
- Dialog widths (`max-w-lg`, `max-w-xl`) adapt well, but their heights do not; there is no `max-h`/`overflow-y-auto`.
- `devicePixelRatio` and OS display-scale changes are not observed. CSS text re-renders correctly, but there is no explicit re-measure or image-resolution adaptation when a window is dragged between monitors.
- `heights` are measured after fonts load for CLI readiness, but the interactive deck has no font-loading hook; a late web font can change line wrapping and therefore the natural height after `fitScale` has already been computed. Svelte's `clientHeight` binding will update it, but there can be a visible resize.

---

## 8. Recommended hardening

Ordered by impact for a two-monitor workflow. None of these are required for the current design to work; they close the gaps above.

1. **Set `minWidth`/`minHeight` in `tauri.conf.json`** (for example 960×600) and restore/maximize the last window geometry. This removes the 800×600 first impression and the unusable-scale tail.
2. **Clamp the final scale** to a legible range and surface a warning when a slide had to shrink below it, rather than silently rendering 8 px text. Keeping `fitScale` but adding a floor plus a "split this slide" hint preserves the uniform-deck property.
3. **Measure width as well as height.** Report `scrollWidth` from the article; if any slide exceeds the design content width, either scale it horizontally (breaking uniformity) or wrap it in an `overflow-x: auto` container. At minimum, add `max-width: 100%` for images/video and `overflow-x: auto` for tables in `app.css`.
4. **Give the rail a viewport-aware layout.** Compute the active indicator from the actual rendered dot positions, and make the rail scroll or compress when `slides.length × 48` exceeds the available height.
5. **Allow a scroll fallback on short windows.** Replace blanket `html { overflow: hidden }` with per-route control, or add `max-height: calc(100vh - 2rem)` + `overflow-y: auto` to dialogs and the error/home screens.
6. **Add viewport checks to CI.** The export gate currently fixes 1280×720. A small browser test at 800×600, 1366×768, 1920×1080, and 2560×1440 could assert: one slide per viewport, no clipped content, `fitScale` computed, and the current slide retained after a resize.
7. **Constrain and serve media at display size.** Add `img, video { max-width: 100%; height: auto }` and consider capturing intrinsic dimensions so the deck can warn about images that will be upscaled beyond their source resolution on a 27"/4K display.

---

## 9. Verification recipe

To confirm the behaviour on the two machines without changing code:

1. Open a deck and resize the window continuously from 800×600 to full screen. The active slide should stay anchored, and a single slide should always fill exactly one viewport.
2. Check a slide with a paragraph at its natural length on both screens. The line breaks should be identical; only the size changes.
3. Add one deliberately dense slide and compare base text size on the laptop and the 27" screen. If the laptop text becomes too small, that is §7.4, not a layout failure.
4. Test a 30-slide deck at 768 px viewport height and inspect the rail for overflow (§7.3).
5. Export the same deck to PDF from both machines and compare pages; both should be 960×540 pt with identical layout, regardless of window size.
6. In the HTML export, resize the browser window and press `F` for fullscreen; the runtime should re-scale and keep the current slide.

---

## 10. File map

| File | Responsive responsibility |
| --- | --- |
| `src/routes/view-slides/shared.svelte.ts` | Design constants (`DESIGN_W`, `DESIGN_H`, `VIEWPORT_PADDING`) and shared deck state. |
| `src/routes/view-slides/+page.svelte` | Window tracking, width scale, per-slide height collection, deck-wide `fitScale`, print mode. |
| `src/routes/view-slides/Slide.svelte` | Fixed 1280 px stage, transform scaling, clipping, natural-height measurement. |
| `src/routes/view-slides/NavBar.svelte` | Resize re-anchoring, rail positioning and viewport-height tracking. |
| `src/routes/view-slides/+layout.svelte` | Arrow-key navigation; scroll suppression that keeps one slide per viewport. |
| `src/app.css` | Global `overflow-hidden`, prose wrapping rules, and fixed 1280×720 print pagination. |
| `src/lib/export/export.svelte.ts` | Enters/leaves `printMode`; guarantees export ignores the window scale. |
| `src/lib/export/standalone.ts` | Mirrors the same scaling algorithm in exported HTML, with resize/print hooks. |
| `src-tauri/src/cli/gui.rs` | Pins CLI export to a logical 1280×720 viewport. |
| `src-tauri/tauri.conf.json` | Default 800×600 window; no minimum size or geometry persistence. |
| `src/lib/tutorial/TutorialOverlay.svelte`, `src/lib/updates/UpdateDialog.svelte` | Conventional max-width dialogs; no height overflow handling. |
