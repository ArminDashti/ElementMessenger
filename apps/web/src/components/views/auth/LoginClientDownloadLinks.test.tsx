/*
Copyright 2026 Armin Dashti

SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial
Please see LICENSE in the repository root for full details.
*/

// @vitest-environment happy-dom

import { describe, it, expect, afterEach } from "vitest";
import React from "react";
import { render, screen } from "test-utils-rtl";

import SdkConfig from "../../../SdkConfig";
import { LoginClientDownloadLinks } from "./LoginClientDownloadLinks";

describe("LoginClientDownloadLinks", () => {
    afterEach(() => {
        SdkConfig.reset();
    });

    it("renders platform download links from config", () => {
        SdkConfig.put({
            desktop_builds: {
                available: true,
                url_win64: "https://example.org/windows.exe",
                url_macos: "https://example.org/mac.dmg",
            },
            mobile_builds: {
                ios: "https://example.org/ios",
                android: "https://example.org/android",
            },
        });

        render(<LoginClientDownloadLinks />);

        expect(screen.getByRole("navigation", { name: "Download the app" })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Windows (64-bit)" })).toHaveAttribute(
            "href",
            "https://example.org/windows.exe",
        );
        expect(screen.getByRole("link", { name: "Mac" })).toHaveAttribute("href", "https://example.org/mac.dmg");
        expect(screen.getByRole("link", { name: "iOS" })).toHaveAttribute("href", "https://example.org/ios");
        expect(screen.getByRole("link", { name: "Android" })).toHaveAttribute("href", "https://example.org/android");
    });

    it("renders nothing when no download URLs are configured", () => {
        SdkConfig.put({
            desktop_builds: {
                available: false,
                url_win64: "",
                url_macos: "",
            },
            mobile_builds: {
                ios: "",
                android: "",
            },
        });

        const { container } = render(<LoginClientDownloadLinks />);
        expect(container).toBeEmptyDOMElement();
    });
});
