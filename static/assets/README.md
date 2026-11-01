# Original UI artwork

Generated with the built-in `image_gen` tool for this project. The reference
screenshots informed the atmosphere and layout; no reference image was used as
an edit target. Neither asset is an official Supercell logo or game asset.
Existing card images remain external Supercell materials, as described in the
root README. No claim of legal clearance is made for third-party materials.

- `arena.webp`: generated at 1536 × 1024, converted to WebP at quality 85.
- `emblem.png`: generated on a transparent background, resized to 256 × 256,
  preserving alpha. Retained, but currently replaced by the project author's approved logo.
- Other UI icons and ribbons are SVG/CSS, not generated bitmaps.
- Font source: Google Fonts `ofl/barlow` and `ofl/barlowcondensed` on GitHub.
  Font licenses are in `../fonts/`.

## Arena prompt

Create a wide landscape website background illustration, no text, no UI, no logo. Original fantasy tournament arena at blue hour, hand painted polished game environment, massive sandstone and slate walls framing far left and far right, warm amber braziers, teal blue pennants with abstract diamond embroidery, distant mountainous landscape and stars. Center 75 percent very dark deep navy open sky, low detail to sit behind opaque web panels. View from inside an arena, slightly elevated. Rich brushwork, believable crafted stone, restrained colors midnight blue and warm gold. Must be an entirely original environment, no recognizable game castles, no crowns or copyrighted characters. Landscape 1536x1024.

## Emblem prompt

A single original small fantasy tournament emblem, isolated on a truly transparent background. A faceted golden six-sided medal, beveled warm brass rim, deep blue enamel center containing three ivory playing-card silhouettes fanned around a small amber four-point star. NO CROWN, no shield shape, no text, no letters, no existing game logos. Hand-painted polished 3D game UI prop, frontal view, readable at 80 pixels, crisp contours, subtle depth, amber highlights, midnight blue shadows. Centered with small transparent margins. Original design unrelated to any existing brand.


## Retro 2016 additions

- `fortress-banner.webp`: original artwork generated with the built-in
  `image_gen` tool, 2172 × 724, converted to WebP at quality 85. Displayed only
  inside the shallow header, never as the page background. The mockups are
  layout references, not copied backgrounds. This is not an official game castle.
- `paper.svg`: project-authored, repeating SVG grain at low opacity. Original
  code covered by the repository's MIT license; no third-party paper texture.
- The earlier `arena.webp` and `emblem.png` remain unused. The header uses
  the project author's approved logo, documented below.
- `../fonts/LilitaOne-Regular.ttf`: unmodified font from
  https://github.com/google/fonts/tree/main/ofl/lilitaone . Copyright 2011
  Juan Montoreano, Reserved Font Name Lilita. The complete SIL OFL 1.1 and
  copyright notice are bundled in `../fonts/OFL-LilitaOne.txt`. The license's
  permission to embed and redistribute with software was checked before use.
  This font is retained but inactive: the live UI uses system Trebuchet MS /
  Verdana / Arial without webfont requests. No original or unofficial game font
  is included.

### Fortress banner prompt

Use case: stylized-concept. Asset type: small panoramic header background for an original retro fantasy fan website, circa 2013–2016. A peaceful distant hilltop fortress with square stone towers, tiny muted blue and ochre pennants, green hills, pale blue daylight sky and a few soft clouds. Original architecture, no recognizable existing game castles. Composition: extremely wide panorama, fortress in the right half, left half quieter blue sky and soft faraway hills for an HTML title overlay. Hand-painted simple game illustration, restrained detail, slightly pixel-era texture, not photorealistic, no characters, no crowns, no logos, no text, no UI, no frames, no button mockups. Keep distant architecture around the horizontal middle so it survives a shallow banner crop. This image will appear only as a 120px-tall header, not a full-screen scene. Wide landscape 3:1.


## Project author's approved logo

The composition was provided by the project author as an Inkscape SVG and PNG.
It incorporates a separately supplied crown asset; it is **not described as
entirely original artwork or covered in full by the repository's MIT license**.
No colors, shapes, layout, or text were changed during integration.

### Supplied files

| Supplied file | Format / dimensions | Integration |
| --- | --- | --- |
| `assets/icon.svg` | SVG, width/height 512, viewBox `0 0 512 512`, 11,583 bytes | Exact source copy: `logo-source.svg` |
| `assets/LogoCRDR` (no extension) | PNG, RGBA, 512×512, 37,124 bytes | Exact binary copy: `logo.png`; header and favicon |
| `assets/42217.svg` | Crown SVG, 1280×668 viewBox, 2,347 bytes | Exact copy: `42217.svg`; not displayed separately |
| root `icon.svg` | SVG, 512×512, 11,580 bytes | Preserved; only Inkscape export-filename metadata differs from `assets/icon.svg` |

The source SVG has no images, hrefs, scripts, or external font declarations.
It contains live `<text>` / `<tspan>` for `CRDR` and `?` with font-family
`Lilita One`. This is a system-font dependency, not a bundled font. It must not
be used as a portable finished SVG until text is converted to paths using the
chosen font. The original files are preserved; conversion has not been performed
without the author's approval. No substitute font is used in the approved PNG.
Both the source SVG rendering and supplied PNG have transparent backgrounds.
The PNG's alpha spans 0–255 and all four corners are fully transparent.

All published references are relative under `./static/assets/`, so the logo
and favicon are included by the existing GitHub Pages packaging workflow.
The supplied 512px PNG is used as-is for the favicon; tiny text can be difficult
to read at 32px. A simplified icon can be supplied by the author later.

### Crown rights and attribution: unresolved

No source URL, creator credit, license name, license terms, or required
attribution was included with `assets/42217.svg`. Its metadata says only
“Created by potrace 1.15, written by Peter Selinger 2001-2017”; that identifies
tracing software and does not establish the crown's creator or license.

The author needs to supply the original source URL, the creator/rightsholder,
the license name and link or permission terms, and the exact required credit
(including modification notices if required). Add the verified attribution here
once supplied. No license or ownership is inferred from the filename, the
tracing-tool metadata, or the general fan-content disclaimer.
