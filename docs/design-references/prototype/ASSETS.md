# Asset provenance

All runtime assets are local. The preview downloads no fonts, images, scripts, or styles from an
external host. No third-party UI kit was installed.

## Fonts

IBM Plex Sans variable font and IBM Plex Sans Arabic Regular/SemiBold are used under the
SIL Open Font License. The accompanying notices are preserved in `assets/OFL-Latin.txt` and
`assets/OFL-Arabic.txt`. Sources retrieved 2026-09-21:

- [Latin family source](https://github.com/google/fonts/tree/main/ofl/ibmplexsans)
- [Arabic family source](https://github.com/google/fonts/tree/main/ofl/ibmplexsansarabic)
- [Upstream IBM Plex project](https://github.com/IBM/plex)

Local files: `assets/plex-sans.ttf`, `assets/plex-arabic-Regular.ttf`, and
`assets/plex-arabic-SemiBold.ttf`. Only filenames were changed; font binaries were not modified.

## Original fictional product photography

`assets/products.png` was created with the built-in image-generation tool on 2026-09-21. It depicts
fictional, unbranded groceries for this synthetic prototype. It does not represent real product
packaging or a production catalog. The original image is preserved; CSS background positioning
selects one quadrant per product, without modifying the raster.

Exact generation prompt:

> Create a single square product photography contact sheet for a fictional Lebanese grocery wholesaler's UI prototype. Exact layout: 2 by 2 equal square cells without gutters or borders. Every cell background is identical very light cool porcelain #F5F7FA. In each cell one centered upright product photographed in elegant bright diffused daylight, soft realistic grounding shadows, plenty of whitespace, entire product in frame with 15% margins. TOP LEFT: dark olive-green glass 750ml olive oil bottle, short black screw cap, cream paper label with simple blue olive branch line illustration, label text only 'OLIVE OIL'. TOP RIGHT: tall transparent pale-blue mineral water 1.5L plastic bottle with blue cap, very minimal white and cobalt label, text only 'WATER'. BOTTOM LEFT: a cream kraft 1kg rice bag, blue paper band, small transparent window showing rice, text only 'RICE'. BOTTOM RIGHT: a sophisticated ivory rectangular carton of a six pack of small drinking water bottles, subtle cobalt blue linear wave motif, text only 'WATER'. All fictional generic unbranded goods, absolutely no real company logos, no prices, no UI, no props, no people. Premium yet everyday B2B grocery product photography, crisp legible silhouettes, natural photographic realism. Product arrangement for CSS sprite use, each object stays entirely inside its own quadrant.

## Interface graphics

The existing connected-stop Tawzeevo wordmark concept is preserved as native CSS geometry.
Interface icons are simple local inline SVG geometry authored for the prototype. The sample shop
uses a fictional Arabic initial, not a replacement Tawzeevo logo.

UI screenshots under `screenshots/` are actual browser captures from the verification scripts.
They are not generated mockups. All visible account, contact, invoice and order content is synthetic.

## Public-entry line illustrations

The local inline SVG paths in `entry.js` are authored for this prototype. No icon dependency,
external illustration or stock artwork is loaded. They depict familiar distribution objects
and reuse the existing Daylight stroke treatment. The Tawzeevo three-node mark is retained.
