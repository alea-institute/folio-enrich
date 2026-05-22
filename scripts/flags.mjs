// Locale -> inline-SVG flag logic for the translation pills.
//
// Pure, testable module mirroring the style of scripts/contrast-audit.mjs.
// The same FLAG_SVG map + helpers are inlined into frontend/index.html
// (single-file frontend, no build step) — keep the two byte-identical so
// these unit tests stay authoritative.
//
// Flags: lipis/flag-icons, MIT (c) 2013 Panayiotis Lipiridis.
// See LICENSES/flag-icons-LICENSE.txt
//
// Vendoring rules applied to every SVG (Pitfall 2):
//   - strip the wrapper id="flag-icons-XX"
//   - namespace internal ids (e.g. jp-a -> fi-jp-a) and update url(#...) refs
//   - add aria-hidden="true" focusable="false" (the wrapper span carries the label)
// ES and MX are trimmed stripe-only variants (Pitfall 1): the coat of arms /
// emblem is a sub-pixel smudge at ~16px, so only the colored bands are kept.

export const FLAG_SVG = {
  de: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#fc0" d="M0 320h640v160H0z"/><path fill="#000001" d="M0 0h640v160H0z"/><path fill="red" d="M0 160h640v160H0z"/></svg>',
  ca: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#fff" d="M150.1 0h339.7v480H150z"/><path fill="#d52b1e" d="M-19.7 0h169.8v480H-19.7zm509.5 0h169.8v480H489.9zM201 232l-13.3 4.4 61.4 54c4.7 13.7-1.6 17.8-5.6 25l66.6-8.4-1.6 67 13.9-.3-3.1-66.6 66.7 8c-4.1-8.7-7.8-13.3-4-27.2l61.3-51-10.7-4c-8.8-6.8 3.8-32.6 5.6-48.9 0 0-35.7 12.3-38 5.8l-9.2-17.5-32.6 35.8c-3.5.9-5-.5-5.9-3.5l15-74.8-23.8 13.4q-3.2 1.3-5.2-2.2l-23-46-23.6 47.8q-2.8 2.5-5 .7L264 130.8l13.7 74.1c-1.1 3-3.7 3.8-6.7 2.2l-31.2-35.3c-4 6.5-6.8 17.1-12.2 19.5s-23.5-4.5-35.6-7c4.2 14.8 17 39.6 9 47.7"/></svg>',
  gb: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#012169" d="M0 0h640v480H0z"/><path fill="#FFF" d="m75 0 244 181L562 0h78v62L400 241l240 178v61h-80L320 301 81 480H0v-60l239-178L0 64V0z"/><path fill="#C8102E" d="m424 281 216 159v40L369 281zm-184 20 6 35L54 480H0zM640 0v3L391 191l2-44L590 0zM0 0l239 176h-60L0 42z"/><path fill="#FFF" d="M241 0v480h160V0zM0 160v160h640V160z"/><path fill="#C8102E" d="M0 193v96h640v-96zM273 0v480h96V0z"/></svg>',
  // US — marker-based 50-star field replaced with explicit <path> stars (no
  // marker/url(#) so FLAG-02 holds): 9 alternating 6/5 rows in the blue canton.
  us: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#bd3d44" d="M0 0h640v480H0"/><path stroke="#fff" stroke-width="37" d="M0 55.3h640M0 129h640M0 203h640M0 277h640M0 351h640M0 425h640"/><path fill="#192f5d" d="M0 0h364.8v258.5H0"/><path fill="#fff" d="M30.4 18.9 L32 23.7 L37.1 23.7 L32.9 26.7 L34.5 31.5 L30.4 28.5 L26.3 31.5 L27.9 26.7 L23.7 23.7 L28.8 23.7zM91.2 18.9 L92.8 23.7 L97.9 23.7 L93.7 26.7 L95.3 31.5 L91.2 28.5 L87.1 31.5 L88.7 26.7 L84.5 23.7 L89.6 23.7zM152 18.9 L153.6 23.7 L158.7 23.7 L154.5 26.7 L156.1 31.5 L152 28.5 L147.9 31.5 L149.5 26.7 L145.3 23.7 L150.4 23.7zM212.8 18.9 L214.4 23.7 L219.5 23.7 L215.3 26.7 L216.9 31.5 L212.8 28.5 L208.7 31.5 L210.3 26.7 L206.1 23.7 L211.2 23.7zM273.6 18.9 L275.2 23.7 L280.3 23.7 L276.1 26.7 L277.7 31.5 L273.6 28.5 L269.5 31.5 L271.1 26.7 L266.9 23.7 L272 23.7zM334.4 18.9 L336 23.7 L341.1 23.7 L336.9 26.7 L338.5 31.5 L334.4 28.5 L330.3 31.5 L331.9 26.7 L327.7 23.7 L332.8 23.7zM60.8 44.7 L62.4 49.5 L67.5 49.5 L63.3 52.5 L64.9 57.4 L60.8 54.4 L56.7 57.4 L58.3 52.5 L54.1 49.5 L59.2 49.5zM121.6 44.7 L123.2 49.5 L128.3 49.5 L124.1 52.5 L125.7 57.4 L121.6 54.4 L117.5 57.4 L119.1 52.5 L114.9 49.5 L120 49.5zM182.4 44.7 L184 49.5 L189.1 49.5 L184.9 52.5 L186.5 57.4 L182.4 54.4 L178.3 57.4 L179.9 52.5 L175.7 49.5 L180.8 49.5zM243.2 44.7 L244.8 49.5 L249.9 49.5 L245.7 52.5 L247.3 57.4 L243.2 54.4 L239.1 57.4 L240.7 52.5 L236.5 49.5 L241.6 49.5zM304 44.7 L305.6 49.5 L310.7 49.5 L306.5 52.5 L308.1 57.4 L304 54.4 L299.9 57.4 L301.5 52.5 L297.3 49.5 L302.4 49.5zM30.4 70.6 L32 75.4 L37.1 75.4 L32.9 78.4 L34.5 83.2 L30.4 80.2 L26.3 83.2 L27.9 78.4 L23.7 75.4 L28.8 75.4zM91.2 70.6 L92.8 75.4 L97.9 75.4 L93.7 78.4 L95.3 83.2 L91.2 80.2 L87.1 83.2 L88.7 78.4 L84.5 75.4 L89.6 75.4zM152 70.6 L153.6 75.4 L158.7 75.4 L154.5 78.4 L156.1 83.2 L152 80.2 L147.9 83.2 L149.5 78.4 L145.3 75.4 L150.4 75.4zM212.8 70.6 L214.4 75.4 L219.5 75.4 L215.3 78.4 L216.9 83.2 L212.8 80.2 L208.7 83.2 L210.3 78.4 L206.1 75.4 L211.2 75.4zM273.6 70.6 L275.2 75.4 L280.3 75.4 L276.1 78.4 L277.7 83.2 L273.6 80.2 L269.5 83.2 L271.1 78.4 L266.9 75.4 L272 75.4zM334.4 70.6 L336 75.4 L341.1 75.4 L336.9 78.4 L338.5 83.2 L334.4 80.2 L330.3 83.2 L331.9 78.4 L327.7 75.4 L332.8 75.4zM60.8 96.4 L62.4 101.2 L67.5 101.2 L63.3 104.2 L64.9 109.1 L60.8 106.1 L56.7 109.1 L58.3 104.2 L54.1 101.2 L59.2 101.2zM121.6 96.4 L123.2 101.2 L128.3 101.2 L124.1 104.2 L125.7 109.1 L121.6 106.1 L117.5 109.1 L119.1 104.2 L114.9 101.2 L120 101.2zM182.4 96.4 L184 101.2 L189.1 101.2 L184.9 104.2 L186.5 109.1 L182.4 106.1 L178.3 109.1 L179.9 104.2 L175.7 101.2 L180.8 101.2zM243.2 96.4 L244.8 101.2 L249.9 101.2 L245.7 104.2 L247.3 109.1 L243.2 106.1 L239.1 109.1 L240.7 104.2 L236.5 101.2 L241.6 101.2zM304 96.4 L305.6 101.2 L310.7 101.2 L306.5 104.2 L308.1 109.1 L304 106.1 L299.9 109.1 L301.5 104.2 L297.3 101.2 L302.4 101.2zM30.4 122.3 L32 127.1 L37.1 127.1 L32.9 130.1 L34.5 134.9 L30.4 131.9 L26.3 134.9 L27.9 130.1 L23.7 127.1 L28.8 127.1zM91.2 122.3 L92.8 127.1 L97.9 127.1 L93.7 130.1 L95.3 134.9 L91.2 131.9 L87.1 134.9 L88.7 130.1 L84.5 127.1 L89.6 127.1zM152 122.3 L153.6 127.1 L158.7 127.1 L154.5 130.1 L156.1 134.9 L152 131.9 L147.9 134.9 L149.5 130.1 L145.3 127.1 L150.4 127.1zM212.8 122.3 L214.4 127.1 L219.5 127.1 L215.3 130.1 L216.9 134.9 L212.8 131.9 L208.7 134.9 L210.3 130.1 L206.1 127.1 L211.2 127.1zM273.6 122.3 L275.2 127.1 L280.3 127.1 L276.1 130.1 L277.7 134.9 L273.6 131.9 L269.5 134.9 L271.1 130.1 L266.9 127.1 L272 127.1zM334.4 122.3 L336 127.1 L341.1 127.1 L336.9 130.1 L338.5 134.9 L334.4 131.9 L330.3 134.9 L331.9 130.1 L327.7 127.1 L332.8 127.1zM60.8 148.1 L62.4 152.9 L67.5 152.9 L63.3 155.9 L64.9 160.8 L60.8 157.8 L56.7 160.8 L58.3 155.9 L54.1 152.9 L59.2 152.9zM121.6 148.1 L123.2 152.9 L128.3 152.9 L124.1 155.9 L125.7 160.8 L121.6 157.8 L117.5 160.8 L119.1 155.9 L114.9 152.9 L120 152.9zM182.4 148.1 L184 152.9 L189.1 152.9 L184.9 155.9 L186.5 160.8 L182.4 157.8 L178.3 160.8 L179.9 155.9 L175.7 152.9 L180.8 152.9zM243.2 148.1 L244.8 152.9 L249.9 152.9 L245.7 155.9 L247.3 160.8 L243.2 157.8 L239.1 160.8 L240.7 155.9 L236.5 152.9 L241.6 152.9zM304 148.1 L305.6 152.9 L310.7 152.9 L306.5 155.9 L308.1 160.8 L304 157.8 L299.9 160.8 L301.5 155.9 L297.3 152.9 L302.4 152.9zM30.4 174 L32 178.8 L37.1 178.8 L32.9 181.8 L34.5 186.6 L30.4 183.6 L26.3 186.6 L27.9 181.8 L23.7 178.8 L28.8 178.8zM91.2 174 L92.8 178.8 L97.9 178.8 L93.7 181.8 L95.3 186.6 L91.2 183.6 L87.1 186.6 L88.7 181.8 L84.5 178.8 L89.6 178.8zM152 174 L153.6 178.8 L158.7 178.8 L154.5 181.8 L156.1 186.6 L152 183.6 L147.9 186.6 L149.5 181.8 L145.3 178.8 L150.4 178.8zM212.8 174 L214.4 178.8 L219.5 178.8 L215.3 181.8 L216.9 186.6 L212.8 183.6 L208.7 186.6 L210.3 181.8 L206.1 178.8 L211.2 178.8zM273.6 174 L275.2 178.8 L280.3 178.8 L276.1 181.8 L277.7 186.6 L273.6 183.6 L269.5 186.6 L271.1 181.8 L266.9 178.8 L272 178.8zM334.4 174 L336 178.8 L341.1 178.8 L336.9 181.8 L338.5 186.6 L334.4 183.6 L330.3 186.6 L331.9 181.8 L327.7 178.8 L332.8 178.8zM60.8 199.8 L62.4 204.6 L67.5 204.6 L63.3 207.6 L64.9 212.5 L60.8 209.5 L56.7 212.5 L58.3 207.6 L54.1 204.6 L59.2 204.6zM121.6 199.8 L123.2 204.6 L128.3 204.6 L124.1 207.6 L125.7 212.5 L121.6 209.5 L117.5 212.5 L119.1 207.6 L114.9 204.6 L120 204.6zM182.4 199.8 L184 204.6 L189.1 204.6 L184.9 207.6 L186.5 212.5 L182.4 209.5 L178.3 212.5 L179.9 207.6 L175.7 204.6 L180.8 204.6zM243.2 199.8 L244.8 204.6 L249.9 204.6 L245.7 207.6 L247.3 212.5 L243.2 209.5 L239.1 212.5 L240.7 207.6 L236.5 204.6 L241.6 204.6zM304 199.8 L305.6 204.6 L310.7 204.6 L306.5 207.6 L308.1 212.5 L304 209.5 L299.9 212.5 L301.5 207.6 L297.3 204.6 L302.4 204.6zM30.4 225.7 L32 230.5 L37.1 230.5 L32.9 233.5 L34.5 238.3 L30.4 235.3 L26.3 238.3 L27.9 233.5 L23.7 230.5 L28.8 230.5zM91.2 225.7 L92.8 230.5 L97.9 230.5 L93.7 233.5 L95.3 238.3 L91.2 235.3 L87.1 238.3 L88.7 233.5 L84.5 230.5 L89.6 230.5zM152 225.7 L153.6 230.5 L158.7 230.5 L154.5 233.5 L156.1 238.3 L152 235.3 L147.9 238.3 L149.5 233.5 L145.3 230.5 L150.4 230.5zM212.8 225.7 L214.4 230.5 L219.5 230.5 L215.3 233.5 L216.9 238.3 L212.8 235.3 L208.7 238.3 L210.3 233.5 L206.1 230.5 L211.2 230.5zM273.6 225.7 L275.2 230.5 L280.3 230.5 L276.1 233.5 L277.7 238.3 L273.6 235.3 L269.5 238.3 L271.1 233.5 L266.9 230.5 L272 230.5zM334.4 225.7 L336 230.5 L341.1 230.5 L336.9 233.5 L338.5 238.3 L334.4 235.3 L330.3 238.3 L331.9 233.5 L327.7 230.5 L332.8 230.5z"/></svg>',
  // ES — trimmed stripe-only (coat of arms removed; invisible at 16px). Hex from raw es.svg header.
  es: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#AA151B" d="M0 0h640v480H0z"/><path fill="#F1BF00" d="M0 120h640v240H0z"/></svg>',
  // MX — trimmed stripe-only (eagle emblem removed). Band hex copied from raw mx.svg (#006847 / #fff / #ce1126).
  mx: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#fff" d="M0 0h640v480H0z"/><path fill="#006847" d="M0 0h213.3v480H0z"/><path fill="#ce1126" d="M426.7 0H640v480H426.7z"/></svg>',
  fr: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#000091" d="M0 0h213.3v480H0z"/><path fill="#fff" d="M213.3 0h213.4v480H213.3z"/><path fill="#e1000f" d="M426.7 0H640v480H426.7z"/></svg>',
  // IL — wrapper clipPath/url(#) dropped (content already fits the viewBox at
  // 16px; clipping was cosmetic) so no url( token remains (FLAG-02).
  il: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><g fill-rule="evenodd" transform="translate(82.1)scale(.94)"><path fill="#fff" d="M619.4 512H-112V0h731.4z"/><path fill="#0038b8" d="M619.4 115.2H-112V48h731.4zm0 350.5H-112v-67.2h731.4zm-483-275 110.1 191.6L359 191.6z"/><path fill="#fff" d="m225.8 317.8 20.9 35.5 21.4-35.3z"/><path fill="#0038b8" d="M136 320.6 246.2 129l112.4 190.8z"/><path fill="#fff" d="m225.8 191.6 20.9-35.5 21.4 35.4zM182 271.1l-21.7 36 41-.1-19.3-36zm-21.3-66.5 41.2.3-19.8 36.3zm151.2 67 20.9 35.5-41.7-.5zm20.5-67-41.2.3 19.8 36.3zm-114.3 0L189.7 256l28.8 50.3 52.8 1.2 32-51.5-29.6-52z"/></g></svg>',
  in: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#f93" d="M0 0h640v160H0z"/><path fill="#fff" d="M0 160h640v160H0z"/><path fill="#128807" d="M0 320h640v160H0z"/><g transform="matrix(3.2 0 0 3.2 320 240)"><circle r="20" fill="#008"/><circle r="17.5" fill="#fff"/><circle r="3.5" fill="#008"/><g id="fi-in-d"><g id="fi-in-c"><g id="fi-in-b"><g id="fi-in-a" fill="#008"><circle r=".9" transform="rotate(7.5 -8.8 133.5)"/><path d="M0 17.5.6 7 0 2l-.6 5z"/></g><path fill="#008" transform="rotate(15)" d="M0 17.5.6 7 0 2l-.6 5z"/><circle r=".9" fill="#008" transform="rotate(15)rotate(7.5 -8.8 133.5)"/></g><g transform="rotate(30)"><g fill="#008"><circle r=".9" transform="rotate(7.5 -8.8 133.5)"/><path d="M0 17.5.6 7 0 2l-.6 5z"/></g><path fill="#008" transform="rotate(15)" d="M0 17.5.6 7 0 2l-.6 5z"/><circle r=".9" fill="#008" transform="rotate(15)rotate(7.5 -8.8 133.5)"/></g></g><g transform="rotate(60)"><g fill="#008"><circle r=".9" transform="rotate(7.5 -8.8 133.5)"/><path d="M0 17.5.6 7 0 2l-.6 5z"/></g><path fill="#008" transform="rotate(15)" d="M0 17.5.6 7 0 2l-.6 5z"/><circle r=".9" fill="#008" transform="rotate(15)rotate(7.5 -8.8 133.5)"/><g transform="rotate(30)"><g fill="#008"><circle r=".9" transform="rotate(7.5 -8.8 133.5)"/><path d="M0 17.5.6 7 0 2l-.6 5z"/></g><path fill="#008" transform="rotate(15)" d="M0 17.5.6 7 0 2l-.6 5z"/><circle r=".9" fill="#008" transform="rotate(15)rotate(7.5 -8.8 133.5)"/></g></g></g><g transform="rotate(120)"><g fill="#008"><circle r=".9" transform="rotate(7.5 -8.8 133.5)"/><path d="M0 17.5.6 7 0 2l-.6 5z"/></g><path fill="#008" transform="rotate(15)" d="M0 17.5.6 7 0 2l-.6 5z"/><circle r=".9" fill="#008" transform="rotate(15)rotate(7.5 -8.8 133.5)"/></g><g transform="rotate(-120)"><g fill="#008"><circle r=".9" transform="rotate(7.5 -8.8 133.5)"/><path d="M0 17.5.6 7 0 2l-.6 5z"/></g><path fill="#008" transform="rotate(15)" d="M0 17.5.6 7 0 2l-.6 5z"/><circle r=".9" fill="#008" transform="rotate(15)rotate(7.5 -8.8 133.5)"/></g></g></svg>',
  // JP — clipPath/url(#) and the translated/scaled disc replaced with a plain
  // centered red disc (r=148, the 3/5-height spec); no url( token (FLAG-02).
  jp: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#fff" d="M0 0h640v480H0z"/><circle cx="320" cy="240" r="148" fill="#bc002d"/></svg>',
  br: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><g stroke-width="1pt"><path fill="#229e45" fill-rule="evenodd" d="M0 0h640v480H0z"/><path fill="#f8e509" fill-rule="evenodd" d="m321.4 436 301.5-195.7L319.6 44 17.1 240.7z"/><path fill="#2b49a3" fill-rule="evenodd" d="M452.8 240c0 70.3-57.1 127.3-127.6 127.3A127.4 127.4 0 1 1 452.8 240"/><path fill="#fff" fill-rule="evenodd" d="M323.6 364.2a124 124 0 0 0 87-35.5c-2.3-30.2-41-69-87.3-69.4a127 127 0 0 0-86.7 33.6 124 124 0 0 0 87 71.3"/></g></svg>',
  // CN — five-star <use> references expanded to explicit <path> stars so the
  // markup carries no "<use " / url(#) token (FLAG-02). Coordinates are the
  // flag-icons star transforms applied to the source star path.
  cn: '<svg viewBox="0 0 640 480" aria-hidden="true" focusable="false"><path fill="#ee1c25" d="M0 0h640v480H0z"/><path fill="#ff0" d="M76.8 177.6 L120 48 L163.2 177.6 L48 98.4 L192 98.4z"/><path fill="#ff0" d="M264.2 50.5 L219.7 60.3 L249.4 25.8 L246.5 72.3 L221.8 31.1z"/><path fill="#ff0" d="M309 107.3 L264.2 99.2 L305 78.8 L284.3 120.6 L277.5 73.1z"/><path fill="#ff0" d="M302.5 187.1 L264.9 161.4 L310.4 159.4 L274.5 189.1 L287.7 142.9z"/><path fill="#ff0" d="M246 239.2 L221.3 201 L264 216.8 L219.4 230.2 L249.4 192.8z"/></svg>',
};

// D-03: representative country for language-only locales.
export const LANG_TO_COUNTRY = { he: 'il', hi: 'in', ja: 'jp', zh: 'cn', es: 'es', fr: 'fr' };

// D-02: the 12 bundled country codes (also the FLAG_SVG keys).
const BUNDLED = new Set(['de', 'ca', 'gb', 'us', 'es', 'mx', 'fr', 'il', 'in', 'jp', 'br', 'cn']);

// Self-contained escape helpers (mirror the semantics of the existing
// escapeHtml/escapeAttr in frontend/index.html so node:test stays standalone).
function escapeHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function escapeAttr(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Intl.DisplayNames instances (module-level; native, no dependency).
const _langDN = new Intl.DisplayNames(['en'], { type: 'language' });
const _regionDN = new Intl.DisplayNames(['en'], { type: 'region' });

// Resolve a locale to a bundled ISO-alpha-2 country code, or null.
// Resolves LANG_TO_COUNTRY BEFORE the BUNDLED check so 'he' fixes to 'il' (Pitfall 4).
export function localeToCountry(locale) {
  const parts = (locale || '').toLowerCase().split('-');
  const cc = parts[1] || LANG_TO_COUNTRY[parts[0]] || '';
  return BUNDLED.has(cc) ? cc : null;
}

// Compose a "Language (Country)" accessible label (FLAG-03, D-06).
export function localeLabel(locale) {
  const parts = (locale || '').toLowerCase().split('-');
  const lang = parts[0] || '';
  let out;
  try { out = _langDN.of(lang) || lang; } catch { out = lang; }
  const cc = (parts[1] || LANG_TO_COUNTRY[lang] || '').toUpperCase();
  if (cc) {
    let country;
    try { country = _regionDN.of(cc); } catch { country = null; }
    if (country && country !== cc) out += ` (${country})`;
  }
  return out;
}

// Build the flag markup: a labeled inline-SVG span, or a styled country-code
// fallback pill for any locale without a bundled flag (FLAG-04, never empty).
export function flagMarkup(locale) {
  const cc = localeToCountry(locale);
  const label = localeLabel(locale);
  const svg = cc && FLAG_SVG[cc];
  if (svg) {
    return `<span class="flag" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${svg}</span>`;
  }
  const code = (cc || (locale || '').split('-')[0] || '?').slice(0, 2).toUpperCase();
  return `<span class="flag-fallback" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${escapeHtml(code)}</span>`;
}
