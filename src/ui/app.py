from __future__ import annotations

import os
import sys

# Fix encoding issues on Windows
if sys.platform == "win32":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st
from dotenv import load_dotenv

from src.services.subtitle_service import build_service_from_env


def get_service():
    load_dotenv()
    return build_service_from_env()


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="Persian Subtitle Search", layout="centered")
    st.title("Persian Subtitle Search")
    st.write("Search OpenSubtitles via MCP and download Persian subtitles.")

    movie_name = st.text_input("Movie name")
    year = st.text_input("Year (optional)")
    prefer_lang = st.selectbox("Preferred language", options=["fa", "en"], index=0)
    fallback_to_english = st.checkbox("If no Persian, show English results", value=True)
    translate_to_persian = st.checkbox("Translate non-Persian subtitles to Persian", value=True)

    if "results" not in st.session_state:
        st.session_state.results = []

    service = get_service()

    col_search, col_download = st.columns(2)

    with col_search:
        if st.button("Search"):
            if not movie_name.strip():
                st.warning("Please enter a movie name.")
            else:
                try:
                    status = st.empty()
                    parsed_year = int(year) if year.strip().isdigit() else None
                    results = []

                    # Search preferred language first
                    status.info(f"Searching for {prefer_lang.upper()} subtitles...")
                    try:
                        fa_results = service.search(
                            movie_name=movie_name,
                            year=parsed_year,
                            language=prefer_lang,
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
        st.subheader("Search results")
        labels = []
        for item in st.session_state.results:
            label = f"{item.language} | {item.release or item.file_name or item.subtitle_id}"
            if item.download_count is not None:
                label += f" | downloads: {item.download_count}"
            labels.append(label)

        selection = st.selectbox("Select a subtitle", options=labels)
        selected_idx = labels.index(selection)
        selected = st.session_state.results[selected_idx]

        target_lang = "fa" if translate_to_persian and selected.language != "fa" else selected.language

        if st.button("Download selected"):
            try:
                needs_translation = translate_to_persian and selected.language != "fa"

                if needs_translation:
                    progress_bar = st.progress(0, text="Downloading subtitle...")
                    status_text = st.empty()

                    def update_progress(current: int, total: int, pct: float):
                        progress_bar.progress(int(pct), text=f"Translating to Persian... {int(pct)}%")
                        status_text.text(f"Translating chunk {current}/{total}")

                    result = service.download_selected(
                        movie_name=movie_name,
                        item=selected,
                        target_lang=target_lang,
                        progress_callback=update_progress,
                    )
                    progress_bar.progress(100, text="Translation complete!")
                    status_text.empty()
                else:
                    result = service.download_selected(
                        movie_name=movie_name,
                        item=selected,
                        target_lang=target_lang,
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
