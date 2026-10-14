import math
import random
import time
from pathlib import Path

import streamlit as st


GAME_DURATION = 60
MOLE_DURATION = 1.5
STARTING_LIVES = 3
POINTS_PER_HIT = 10
BOARD_SIZE = 9
ASSET_DIR = Path(__file__).parent
FRAGMENT_REFRESH_SECONDS = 0.1

st.set_page_config(page_title="두더지 잡기", page_icon="🐹")


@st.cache_data(show_spinner=False)
def load_game_image(image_name):
    return (ASSET_DIR / image_name).read_bytes()


def choose_mole_index(previous_index=None):
    available_indices = [
        index for index in range(BOARD_SIZE) if index != previous_index
    ]
    return random.choice(available_indices)


def reset_game():
    st.session_state.game_id = st.session_state.get("game_id", 0) + 1
    st.session_state.score = 0
    st.session_state.lives = STARTING_LIVES
    st.session_state.started_at = None
    st.session_state.mole_started_at = None
    st.session_state.mole_index = None
    st.session_state.mole_id = 0
    st.session_state.game_state = "ready"
    st.session_state.end_reason = None
    st.session_state.remaining_at_end = GAME_DURATION
    st.session_state.refresh_stop_pending = False


def start_game():
    if st.session_state.game_state != "ready":
        return

    now = time.monotonic()
    st.session_state.started_at = now
    st.session_state.mole_started_at = now
    st.session_state.mole_index = random.randrange(BOARD_SIZE)
    st.session_state.mole_id += 1
    st.session_state.game_state = "playing"


def finish_game(reason, now):
    if st.session_state.game_state != "playing":
        return

    elapsed = now - st.session_state.started_at
    st.session_state.remaining_at_end = (
        0 if reason == "time" else max(0, math.ceil(GAME_DURATION - elapsed))
    )
    st.session_state.game_state = "finished"
    st.session_state.end_reason = reason
    st.session_state.mole_index = None
    st.session_state.mole_started_at = None
    st.session_state.refresh_stop_pending = True


def update_game(now):
    if st.session_state.game_state != "playing":
        return

    if now - st.session_state.started_at >= GAME_DURATION:
        finish_game("time", now)
        return

    if now - st.session_state.mole_started_at >= MOLE_DURATION:
        previous_index = st.session_state.mole_index
        st.session_state.lives = max(0, st.session_state.lives - 1)
        st.session_state.mole_id += 1

        if st.session_state.lives == 0:
            finish_game("lives", now)
            return

        st.session_state.mole_index = choose_mole_index(previous_index)
        st.session_state.mole_started_at = now


def remaining_seconds(now):
    if st.session_state.game_state == "ready":
        return GAME_DURATION
    if st.session_state.game_state == "finished":
        return st.session_state.remaining_at_end
    return max(0, math.ceil(GAME_DURATION - (now - st.session_state.started_at)))


def handle_hole_click(index, game_id, mole_id):
    now = time.monotonic()
    update_game(now)

    if (
        st.session_state.game_state != "playing"
        or game_id != st.session_state.game_id
        or mole_id != st.session_state.mole_id
    ):
        return

    if index == st.session_state.mole_index:
        previous_index = st.session_state.mole_index
        st.session_state.score += POINTS_PER_HIT
        st.session_state.mole_id += 1
        st.session_state.mole_index = choose_mole_index(previous_index)
        st.session_state.mole_started_at = now


if "game_state" not in st.session_state:
    reset_game()

st.title("두더지 잡기")
st.caption("두더지를 잡으면 10점, 놓치면 목숨이 하나 줄어요.")
st.markdown(
    """
    <style>
    div[data-testid="stButton"] > button { min-height: 3.25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


if st.session_state.game_state == "ready":
    st.button("게임 시작", type="primary", on_click=start_game)
elif st.session_state.game_state == "finished":
    st.button("다시 시작", type="primary", on_click=reset_game)

refresh_interval = (
    FRAGMENT_REFRESH_SECONDS
    if st.session_state.game_state == "playing"
    else None
)


@st.fragment(run_every=refresh_interval)
def game_board():
    now = time.monotonic()
    update_game(now)
    if st.session_state.refresh_stop_pending:
        st.session_state.refresh_stop_pending = False
        st.rerun()

    remaining = remaining_seconds(now)

    score_col, lives_col, time_col = st.columns(3)
    score_col.metric("현재 점수", st.session_state.score)
    lives_col.metric("라이프", st.session_state.lives)
    time_col.metric("남은 시간", f"{remaining}초")
    st.progress(remaining / GAME_DURATION)

    with st.container(height=72, border=False):
        if st.session_state.game_state == "finished":
            if st.session_state.end_reason == "time":
                st.success(f"시간 종료! 최종 점수: {st.session_state.score}점")
            else:
                st.info(f"목숨을 모두 썼어요. 최종 점수: {st.session_state.score}점")
        elif st.session_state.game_state == "ready":
            st.caption("게임 시작 버튼을 누르면 두더지가 나타나요.")

    for row in range(3):
        columns = st.columns(3)
        for column in range(3):
            index = row * 3 + column
            is_mole = (
                st.session_state.game_state == "playing"
                and index == st.session_state.mole_index
            )
            with columns[column]:
                with st.container(border=True):
                    image_name = "img.png" if is_mole else "hole.png"
                    st.image(load_game_image(image_name), width=120)
                    label = "잡기" if is_mole else f"구멍 {index + 1}"
                    st.button(
                        label,
                        key=(
                            f"hole-{st.session_state.game_id}-"
                            f"{st.session_state.mole_id}-{index}"
                        ),
                        use_container_width=True,
                        type="primary" if is_mole else "secondary",
                        disabled=st.session_state.game_state != "playing",
                        on_click=handle_hole_click,
                        args=(
                            index,
                            st.session_state.game_id,
                            st.session_state.mole_id,
                        ),
                    )


game_board()