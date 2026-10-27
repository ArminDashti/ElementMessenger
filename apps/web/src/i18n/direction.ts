/*
 * Copyright 2026 Element Creations Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only OR GPL-3.0-only OR LicenseRef-Element-Commercial
 * Please see LICENSE files in the repository root for full details.
 */

/**
 * Languages written right to left. Compared on the base subtag, so `fa-IR` counts as `fa`.
 */
const RTL_LANGUAGES = new Set(["ar", "ckb", "dv", "fa", "he", "iw", "ps", "sd", "ug", "ur", "yi"]);

/**
 * @param language A language key, e.g. `fa`
 * @returns whether text in this language is written right to left
 */
export function isRtlLanguage(language: string): boolean {
    return RTL_LANGUAGES.has(language.split("-")[0].toLowerCase());
}

/**
 * Mirror the whole document when the UI language is RTL. The `dir` attribute on `<html>` flips text
 * direction and flex order, which is what moves the space panel and room list to the right. The CSS
 * build mirrors the physical properties (`margin-left`, `border-right`, …) off the same attribute.
 *
 * @param language the language the UI is being displayed in
 */
export function applyDocumentDirection(language: string): void {
    if (typeof document === "undefined") return;
    document.documentElement.setAttribute("dir", isRtlLanguage(language) ? "rtl" : "ltr");
}
