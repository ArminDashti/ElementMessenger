/*
 * Copyright 2026 Element Creations Ltd.
 *
 * SPDX-License-Identifier: AGPL-3.0-only OR GPL-3.0-only OR LicenseRef-Element-Commercial
 * Please see LICENSE files in the repository root for full details.
 */

// @vitest-environment happy-dom

import { describe, it, expect, afterEach } from "vitest";

import { applyDocumentDirection, isRtlLanguage } from "./direction";

describe("isRtlLanguage", () => {
    it.each(["fa", "he", "ar", "ar-EG", "fa-IR"])("treats %s as right to left", (lang) => {
        expect(isRtlLanguage(lang)).toBe(true);
    });

    it.each(["en", "de", "pt-BR", ""])("treats %s as left to right", (lang) => {
        expect(isRtlLanguage(lang)).toBe(false);
    });
});

describe("applyDocumentDirection", () => {
    afterEach(() => {
        document.documentElement.removeAttribute("dir");
    });

    it("mirrors the document for Persian", () => {
        applyDocumentDirection("fa");
        expect(document.documentElement.getAttribute("dir")).toBe("rtl");
    });

    it("restores left to right for other languages", () => {
        applyDocumentDirection("fa");
        applyDocumentDirection("en");
        expect(document.documentElement.getAttribute("dir")).toBe("ltr");
    });
});
