/*
Copyright 2026 Armin Dashti

SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial
Please see LICENSE in the repository root for full details.
*/

import React, { type JSX } from "react";
import { MacIcon, WindowsIcon } from "@vector-im/compound-design-tokens/assets/web/icons";

import SdkConfig from "../../../SdkConfig";
import { _t } from "../../../languageHandler";

interface PlatformLink {
    key: string;
    href: string;
    label: string;
    icon: JSX.Element;
    showLabel: boolean;
}

/**
 * Platform download links shown on the login screen, driven by `desktop_builds` and `mobile_builds` in config.
 */
export function LoginClientDownloadLinks(): JSX.Element | null {
    const { desktop_builds: desktopBuilds, mobile_builds: mobileBuilds } = SdkConfig.get();
    const links: PlatformLink[] = [];

    if (desktopBuilds?.available) {
        const windowsUrl = desktopBuilds.url_win64 ?? desktopBuilds.url_win64arm;
        if (windowsUrl) {
            links.push({
                key: "windows",
                href: windowsUrl,
                label: _t("incompatible_browser|windows_64bit"),
                icon: <WindowsIcon width={24} height={24} />,
                showLabel: true,
            });
        }
        if (desktopBuilds.url_macos) {
            links.push({
                key: "macos",
                href: desktopBuilds.url_macos,
                label: _t("incompatible_browser|macos"),
                icon: <MacIcon width={24} height={24} />,
                showLabel: true,
            });
        }
    }

    if (mobileBuilds?.ios) {
        links.push({
            key: "ios",
            href: mobileBuilds.ios,
            label: _t("auth|client_downloads_ios"),
            icon: (
                <img
                    className="mx_Login_clientDownloadLink_storeBadge"
                    src="themes/element/img/download/apple.svg"
                    alt=""
                    height={32}
                />
            ),
            showLabel: false,
        });
    }
    if (mobileBuilds?.android) {
        links.push({
            key: "android",
            href: mobileBuilds.android,
            label: _t("auth|client_downloads_android"),
            icon: (
                <img
                    className="mx_Login_clientDownloadLink_storeBadge"
                    src="themes/element/img/download/google.svg"
                    alt=""
                    height={32}
                />
            ),
            showLabel: false,
        });
    }

    if (links.length === 0) {
        return null;
    }

    return (
        <nav className="mx_Login_clientDownloads" aria-label={_t("auth|client_downloads_heading")}>
            <p className="mx_Login_clientDownloads_title">{_t("auth|client_downloads_heading")}</p>
            <div className="mx_Login_clientDownloads_links">
                {links.map((link) => (
                    <a
                        key={link.key}
                        className="mx_Login_clientDownloadLink"
                        href={link.href}
                        target="_blank"
                        rel="noreferrer noopener"
                        aria-label={link.label}
                        title={link.label}
                    >
                        {link.icon}
                        {link.showLabel && (
                            <span className="mx_Login_clientDownloadLink_label">{link.label}</span>
                        )}
                    </a>
                ))}
            </div>
        </nav>
    );
}
