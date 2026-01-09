from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Fix encoding issues on Windows
if sys.platform == "win32":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st
from dotenv import load_dotenv

from src.services.subtitle_service import build_service_from_env


def parse_season_episode(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract season and episode numbers from a string like S01E02 or 1x02."""
    if not text:
        return None, None
    # Match S01E02 format
    match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    # Match 1x02 format
    match = re.search(r'(\d{1,2})[xX](\d{1,2})', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def is_tv_show_results(results) -> bool:
    """Check if results appear to be TV show episodes."""
    if not results:
        return False
    tv_count = 0
    for item in results[:10]:  # Check first 10
        text = item.release or item.file_name or ""
        season, episode = parse_season_episode(text)
        if season is not None:
            tv_count += 1
    return tv_count >= len(results[:10]) * 0.5  # At least 50% have season/episode


def group_by_season_episode(results) -> Dict[int, Dict[int, List]]:
    """Group results by season and episode."""
    grouped = defaultdict(lambda: defaultdict(list))
    ungrouped = []

    for item in results:
        text = item.release or item.file_name or ""
        season, episode = parse_season_episode(text)
        if season is not None and episode is not None:
            grouped[season][episode].append(item)
        else:
            ungrouped.append(item)

    return grouped, ungrouped


@st.cache_resource
def get_service(_model: str = None):
    load_dotenv()
    # Temporarily set the environment variable for this service instance
    if _model:
        os.environ["OPENAI_MODEL"] = _model
    return build_service_from_env()


def main() -> None:
    st.set_page_config(page_title="Persian Subtitle Search", layout="centered")
    load_dotenv()

    # Title with settings button
    col_title, col_settings = st.columns([5, 1])
    with col_title:
        st.title("Persian Subtitle Search")
    with col_settings:
        st.write("")  # Spacer
        if st.button("⚙️ Settings", key="open_settings"):
            st.session_state.show_settings = not st.session_state.get("show_settings", False)

    st.write("Search OpenSubtitles via MCP and download Persian subtitles.")

    # Settings dialog
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if st.session_state.get("show_settings", False):
        with st.container():
            st.divider()
            st.subheader("⚙️ Settings")

            openai_model = st.selectbox(
                "OpenAI Translation Model",
                options=["gpt-4o-mini", "gpt-5-mini", "gpt-5-nano", "gpt-5.2", "gpt-oss-120b"],
                index=["gpt-4o-mini", "gpt-5-mini", "gpt-5-nano", "gpt-5.2", "gpt-oss-120b"].index(st.session_state.openai_model) if st.session_state.openai_model in ["gpt-4o-mini", "gpt-5-mini", "gpt-5-nano", "gpt-5.2", "gpt-oss-120b"] else 1,
                help="Select the OpenAI model to use for translating subtitles"
            )
            st.session_state.openai_model = openai_model

            st.info("💡 Tip: Faster models (gpt-5-nano, gpt-4o-mini) are cheaper but may be less accurate. Slower models (gpt-5.2) provide better translation quality.")
            st.divider()

    movie_name = st.text_input("Movie/TV Show name")
    col_year, col_imdb, col_type = st.columns(3)
    with col_year:
        year = st.text_input("Year (optional)")
    with col_imdb:
        imdb_id = st.text_input("IMDB ID (optional)", help="e.g., tt5014882")
    with col_type:
        content_type = st.selectbox(
            "Type",
            options=["all", "movie", "tvshow", "episode"],
            index=0,
            help="Filter by content type"
        )
    prefer_lang = st.selectbox("Preferred language", options=["fa", "en"], index=0)
    fallback_to_english = st.checkbox("If no Persian, show English results", value=True)

    if "results" not in st.session_state:
        st.session_state.results = []

    service = get_service(_model=st.session_state.openai_model)

    col_search, col_download = st.columns(2)

    with col_search:
        if st.button("Search"):
            if not movie_name.strip():
                st.warning("Please enter a movie name.")
            else:
                try:
                    status = st.empty()
                    parsed_year = int(year) if year.strip().isdigit() else None
                    # Parse IMDB ID - remove 'tt' prefix if present and convert to int
                    parsed_imdb = None
                    if imdb_id.strip():
                        imdb_clean = imdb_id.strip().lower().replace("tt", "")
                        if imdb_clean.isdigit():
                            parsed_imdb = int(imdb_clean)
                    # Type filter - None if "all" selected
                    type_filter = content_type if content_type != "all" else None
                    results = []

                    # Search preferred language first
                    status.info(f"Searching for {prefer_lang.upper()} subtitles...")
                    try:
                        fa_results = service.search(
                            movie_name=movie_name,
                            year=parsed_year,
                            language=prefer_lang,
                            imdb_id=parsed_imdb,
                            type=type_filter,
                        )
                        results.extend(fa_results)
                    except Exception as e:
                        st.warning(f"Search for {prefer_lang.upper()} failed: {e}")

                    # When fallback is enabled, also search English
                    if prefer_lang == "fa" and fallback_to_english:
                        status.info("Searching for EN subtitles...")
                        try:
                            en_results = service.search(
                                movie_name=movie_name,
                                year=parsed_year,
                                language="en",
                                imdb_id=parsed_imdb,
                                type=type_filter,
                            )
                            results.extend(en_results)
                        except Exception as e:
                            st.warning(f"Search for EN failed: {e}")

                    status.empty()
                    st.session_state.results = results
                    if not results:
                        st.info("No subtitles found for this movie. Try a different search term or year.")
                except Exception as exc:
                    st.error(str(exc))

    with col_download:
        if st.button("Download best match"):
            if not movie_name.strip():
                st.warning("Please enter a movie name.")
            else:
                try:
                    result = service.download_best(
                        movie_name=movie_name,
                        year=int(year) if year.strip().isdigit() else None,
                        prefer_lang=prefer_lang,
                    )
                    st.success(f"Saved to {result.file_path}")
                    st.download_button(
                        label="Download SRT",
                        data=result.content_bytes,
                        file_name=os.path.basename(result.file_path),
                        mime="application/x-subrip",
                    )
                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.results:
        st.subheader(f"Search results ({len(st.session_state.results)} found)")

        # Check if this is a TV show
        is_tv = is_tv_show_results(st.session_state.results)

        if is_tv:
            # TV Show mode - organized by season/episode
            grouped, ungrouped = group_by_season_episode(st.session_state.results)

            # Filter input
            filter_text = st.text_input(
                "Filter results",
                placeholder="Type to filter (e.g., S01E03, 720p, HDTV...)",
                key="result_filter"
            )

            # Initialize selection state for checkboxes
            if "selected_items" not in st.session_state:
                st.session_state.selected_items = set()

            # Initialize season download state
            if "season_download_data" not in st.session_state:
                st.session_state.season_download_data = {}
            if "selected_download_data" not in st.session_state:
                st.session_state.selected_download_data = None

            # Display organized results
            for season in sorted(grouped.keys()):
                with st.expander(f"Season {season}", expanded=(season == min(grouped.keys()))):
                    # Download All Season button
                    season_episodes = grouped[season]
                    total_episodes = len(season_episodes)
                    season_key = f"season_{season}"

                    # Check if we have already downloaded this season
                    if season_key in st.session_state.season_download_data:
                        zip_data = st.session_state.season_download_data[season_key]
                        zip_filename = f"{movie_name.replace(' ', '_')}_Season_{season}.zip"

                        st.success(f"Season {season} ready for download!")
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.download_button(
                                label=f"Download Season {season} ZIP ({total_episodes} episodes)",
                                data=zip_data,
                                file_name=zip_filename,
                                mime="application/zip",
                                key=f"download_zip_{season}"
                            )
                        with col2:
                            if st.button("Clear", key=f"clear_season_{season}"):
                                del st.session_state.season_download_data[season_key]
                                st.rerun()
                    else:
                        # Two buttons: Download Original and Download + Translate
                        col_orig, col_translate = st.columns(2)

                        with col_orig:
                            download_original_btn = st.button(
                                f"⬇️ Download All (Original)",
                                key=f"download_season_orig_{season}",
                                help=f"Download all {total_episodes} episodes in their original language (fast)",
                                use_container_width=True
                            )

                        with col_translate:
                            download_translate_btn = st.button(
                                f"🔄 Download All + Translate to FA",
                                key=f"download_season_translate_{season}",
                                type="primary",
                                help=f"Download and translate all {total_episodes} episodes to Persian (slower)",
                                use_container_width=True
                            )

                        if download_original_btn or download_translate_btn:
                            # Determine if we should translate
                            should_translate = download_translate_btn
                            try:
                                # Create containers for progress
                                progress_container = st.container()

                                with progress_container:
                                    # Create a zip file in memory
                                    zip_buffer = io.BytesIO()

                                    with st.spinner(f"Preparing to download Season {season}..."):
                                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                            progress_bar = st.progress(0)
                                            status_text = st.empty()

                                            episode_list = sorted(season_episodes.keys())
                                            for idx, episode in enumerate(episode_list):
                                                try:
                                                    items = season_episodes[episode]
                                                    # Get the best item for this episode (highest score/download count)
                                                    best_item = max(items, key=lambda x: (x.score or 0.0, x.download_count or 0))

                                                    # Show download status
                                                    lang_label = best_item.language.upper()
                                                    status_text.info(f"📥 Downloading S{season:02d}E{episode:02d} [{lang_label}]... ({idx + 1}/{total_episodes})")

                                                    # Determine target language based on button clicked
                                                    target_lang = "fa" if should_translate else best_item.language

                                                    # Create a progress callback for translation
                                                    translation_status = st.empty()

                                                    def progress_callback(current: int, total: int, pct: float):
                                                        translation_status.info(f"🔄 Translating S{season:02d}E{episode:02d} to Persian... {int(pct)}% (chunk {current}/{total})")

                                                    # Download the subtitle (with translation if needed)
                                                    result = service.download_selected(
                                                        movie_name=movie_name,
                                                        item=best_item,
                                                        target_lang=target_lang,
                                                        progress_callback=progress_callback if should_translate and best_item.language != "fa" else None,
                                                    )

                                                    translation_status.empty()

                                                    # Add to zip with a meaningful name
                                                    file_name = f"S{season:02d}E{episode:02d}.{target_lang}.srt"
                                                    zip_file.writestr(file_name, result.content_text)

                                                    # Update progress
                                                    progress = (idx + 1) / total_episodes
                                                    progress_bar.progress(progress)
                                                    status_text.success(f"✅ Completed S{season:02d}E{episode:02d} ({idx + 1}/{total_episodes})")
                                                except Exception as ep_error:
                                                    status_text.warning(f"❌ Failed S{season:02d}E{episode:02d}: {str(ep_error)}")
                                                    # Continue with next episode even if one fails
                                                    continue

                                            status_text.success("All episodes downloaded!")
                                            progress_bar.progress(1.0)

                                    # Store the zip data in session state
                                    zip_buffer.seek(0)
                                    st.session_state.season_download_data[season_key] = zip_buffer.getvalue()

                                    # Force a rerun to show the download button
                                    st.rerun()
                            except Exception as exc:
                                st.error(f"Error downloading season: {exc}")

                    st.divider()

                    for episode in sorted(grouped[season].keys()):
                        items = grouped[season][episode]

                        # Apply filter
                        if filter_text:
                            items = [
                                item for item in items
                                if filter_text.lower() in (item.release or "").lower()
                                or filter_text.lower() in (item.file_name or "").lower()
                            ]
                            if not items:
                                continue

                        st.markdown(f"**Episode {episode}** ({len(items)} versions)")

                        for i, item in enumerate(items):
                            release = item.release or item.file_name or item.subtitle_id
                            downloads = f"downloads: {item.download_count}" if item.download_count else ""
                            lang_badge = f"[{item.language.upper()}]"

                            # Create unique identifier for this item
                            item_id = f"s{season}_e{episode}_{i}"

                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.caption(f"{lang_badge} {release} {downloads}")
                            with col2:
                                is_selected = st.checkbox(
                                    "Select",
                                    value=item_id in st.session_state.selected_items,
                                    key=f"check_{item_id}",
                                    label_visibility="collapsed"
                                )
                                if is_selected:
                                    st.session_state.selected_items.add(item_id)
                                    # Store the actual item object for later use
                                    if not hasattr(st.session_state, 'item_map'):
                                        st.session_state.item_map = {}
                                    st.session_state.item_map[item_id] = item
                                elif item_id in st.session_state.selected_items:
                                    st.session_state.selected_items.remove(item_id)

            # Show ungrouped items if any
            if ungrouped:
                if filter_text:
                    ungrouped = [
                        item for item in ungrouped
                        if filter_text.lower() in (item.release or "").lower()
                        or filter_text.lower() in (item.file_name or "").lower()
                    ]
                if ungrouped:
                    with st.expander(f"Other ({len(ungrouped)} items)"):
                        for i, item in enumerate(ungrouped):
                            release = item.release or item.file_name or item.subtitle_id
                            downloads = f"downloads: {item.download_count}" if item.download_count else ""

                            # Create unique identifier for this item
                            item_id = f"other_{i}"

                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.caption(f"[{item.language.upper()}] {release} {downloads}")
                            with col2:
                                is_selected = st.checkbox(
                                    "Select",
                                    value=item_id in st.session_state.selected_items,
                                    key=f"check_{item_id}",
                                    label_visibility="collapsed"
                                )
                                if is_selected:
                                    st.session_state.selected_items.add(item_id)
                                    if not hasattr(st.session_state, 'item_map'):
                                        st.session_state.item_map = {}
                                    st.session_state.item_map[item_id] = item
                                elif item_id in st.session_state.selected_items:
                                    st.session_state.selected_items.remove(item_id)

            # Show download buttons for selected items
            if st.session_state.selected_items:
                st.divider()
                num_selected = len(st.session_state.selected_items)
                st.info(f"✅ {num_selected} subtitle(s) selected")

                # Check if we have a ready download
                if st.session_state.selected_download_data:
                    zip_data, zip_filename = st.session_state.selected_download_data
                    st.success(f"Selected subtitles ready for download!")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.download_button(
                            label=f"Download {num_selected} Selected Subtitle(s)",
                            data=zip_data,
                            file_name=zip_filename,
                            mime="application/zip",
                            key="download_selected_zip"
                        )
                    with col2:
                        if st.button("Clear", key="clear_selected"):
                            st.session_state.selected_download_data = None
                            st.rerun()
                else:
                    col_orig, col_translate = st.columns(2)

                    with col_orig:
                        download_selected_original = st.button(
                            f"⬇️ Download {num_selected} Selected (Original)",
                            key="download_selected_orig",
                            help="Download selected subtitles in their original language (fast)",
                            use_container_width=True
                        )

                    with col_translate:
                        download_selected_translate = st.button(
                            f"🔄 Download {num_selected} Selected + Translate to FA",
                            key="download_selected_translate",
                            type="primary",
                            help="Download and translate selected subtitles to Persian (slower)",
                            use_container_width=True
                        )

                    if download_selected_original or download_selected_translate:
                        should_translate = download_selected_translate
                        try:
                            progress_container = st.container()

                            with progress_container:
                                zip_buffer = io.BytesIO()

                                with st.spinner(f"Preparing to download {num_selected} subtitle(s)..."):
                                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                        progress_bar = st.progress(0)
                                        status_text = st.empty()

                                        item_ids = list(st.session_state.selected_items)
                                        for idx, item_id in enumerate(item_ids):
                                            try:
                                                item = st.session_state.item_map[item_id]

                                                # Show download status
                                                lang_label = item.language.upper()
                                                status_text.info(f"📥 Downloading [{lang_label}] {item.release or item.file_name}... ({idx + 1}/{num_selected})")

                                                # Determine target language
                                                target_lang = "fa" if should_translate else item.language

                                                # Create a progress callback for translation
                                                translation_status = st.empty()

                                                def progress_callback(current: int, total: int, pct: float):
                                                    translation_status.info(f"🔄 Translating... {int(pct)}% (chunk {current}/{total})")

                                                # Download the subtitle
                                                result = service.download_selected(
                                                    movie_name=movie_name,
                                                    item=item,
                                                    target_lang=target_lang,
                                                    progress_callback=progress_callback if should_translate and item.language != "fa" else None,
                                                )

                                                translation_status.empty()

                                                # Add to zip with a meaningful name
                                                safe_name = (item.release or item.file_name or item.subtitle_id).replace("/", "_").replace("\\", "_")
                                                file_name = f"{safe_name}.{target_lang}.srt"
                                                zip_file.writestr(file_name, result.content_text)

                                                # Update progress
                                                progress = (idx + 1) / num_selected
                                                progress_bar.progress(progress)
                                                status_text.success(f"✅ Completed ({idx + 1}/{num_selected})")
                                            except Exception as ep_error:
                                                status_text.warning(f"❌ Failed: {str(ep_error)}")
                                                continue

                                        status_text.success("All selected subtitles downloaded!")
                                        progress_bar.progress(1.0)

                                # Store the zip data
                                zip_buffer.seek(0)
                                zip_filename = f"{movie_name.replace(' ', '_')}_selected_subtitles.zip"
                                st.session_state.selected_download_data = (zip_buffer.getvalue(), zip_filename)

                                # Rerun to show download button
                                st.rerun()
                        except Exception as exc:
                            st.error(f"Error downloading selected subtitles: {exc}")
        else:
            # Movie mode - simple dropdown
            filter_text = st.text_input(
                "Filter results",
                placeholder="Type to filter...",
                key="result_filter"
            )

            filtered_results = st.session_state.results
            if filter_text:
                filtered_results = [
                    item for item in st.session_state.results
                    if filter_text.lower() in (item.release or "").lower()
                    or filter_text.lower() in (item.file_name or "").lower()
                ]

            if filtered_results:
                labels = []
                for item in filtered_results:
                    label = f"{item.language} | {item.release or item.file_name or item.subtitle_id}"
                    if item.download_count is not None:
                        label += f" | downloads: {item.download_count}"
                    labels.append(label)

                selection = st.selectbox("Select a subtitle", options=labels)
                selected_idx = labels.index(selection)
                selected = filtered_results[selected_idx]
            else:
                st.info("No results match your filter.")
                selected = None

            # Download section for selected item (movie mode only)
            if selected:
                st.divider()
                st.markdown(f"**Selected:** {selected.release or selected.file_name}")

                is_non_persian = selected.language != "fa"

                if is_non_persian:
                    col_orig, col_translate = st.columns(2)

                    with col_orig:
                        download_original = st.button(f"Download Original ({selected.language.upper()})")

                    with col_translate:
                        download_translated = st.button("Translate to Persian")

                    if download_original:
                        try:
                            result = service.download_selected(
                                movie_name=movie_name,
                                item=selected,
                                target_lang=selected.language,
                            )
                            st.success(f"Saved to {result.file_path}")
                            st.download_button(
                                label=f"Download SRT ({selected.language.upper()})",
                                data=result.content_bytes,
                                file_name=os.path.basename(result.file_path),
                                mime="application/x-subrip",
                            )
                        except Exception as exc:
                            st.error(str(exc))

                    if download_translated:
                        try:
                            progress_bar = st.progress(0, text="Downloading subtitle...")
                            status_text = st.empty()

                            def update_progress(current: int, total: int, pct: float):
                                progress_bar.progress(int(pct), text=f"Translating to Persian... {int(pct)}%")
                                status_text.text(f"Translating chunk {current}/{total}")

                            result = service.download_selected(
                                movie_name=movie_name,
                                item=selected,
                                target_lang="fa",
                                progress_callback=update_progress,
                            )
                            progress_bar.progress(100, text="Translation complete!")
                            status_text.empty()

                            st.success(f"Saved to {result.file_path}")
                            st.download_button(
                                label="Download SRT (Persian)",
                                data=result.content_bytes,
                                file_name=os.path.basename(result.file_path),
                                mime="application/x-subrip",
                            )
                        except Exception as exc:
                            st.error(str(exc))
                else:
                    if st.button("Download selected"):
                        try:
                            result = service.download_selected(
                                movie_name=movie_name,
                                item=selected,
                                target_lang="fa",
                            )
                            st.success(f"Saved to {result.file_path}")
                            st.download_button(
                                label="Download SRT",
                                data=result.content_bytes,
                                file_name=os.path.basename(result.file_path),
                                mime="application/x-subrip",
                            )
                        except Exception as exc:
                            st.error(str(exc))


main()
