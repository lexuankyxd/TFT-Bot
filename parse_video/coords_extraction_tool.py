#!/usr/bin/env python3
"""
Interactive video coordinate extraction tool with zoom and pan.

Controls:
- Space: Play / Pause
- Right mouse button (hold & drag): Pan
- Mouse wheel (or wheel buttons 4/5): Zoom centered at mouse position
- + / -: Zoom in/out centered at mouse position
- Left / Right arrow: Jump backward/forward by `skip` frames while paused
- R: Reset zoom & pan
- X: Save current frame as image.png (overwrites existing)
- Esc or window close: Exit

UI:
- Top-left overlay shows: Zoom level, Frame index, FPS, Instructions
- When hovering over the video, shows the (x, y) coordinate in the original video space
- Progress bar at the bottom shows current position; click to seek
"""

import sys

import cv2
import numpy as np
import pygame

pygame.init()
pygame.font.init()

# CONFIG
VIDEO_PATH = "vids/a.mp4"
WINDOW_TITLE = "Coords Extraction Tool - Zoom & Pan"
FONT_NAME = "arial"
FONT_SIZE = 18
INFO_BG = (0, 0, 0, 140)  # translucent-like background (we'll simulate with rect)
TEXT_COLOR = (255, 255, 255)
FPS_DRAW_COLOR = (200, 200, 200)

# Zoom/pan params
ZOOM_STEP = 1.15
MIN_ZOOM = 0.2
MAX_ZOOM = 6.0
PAN_BUTTON = 3  # right mouse button for panning

# Progress bar params
BAR_HEIGHT = 20
BAR_COLOR_BG = (100, 100, 100)
BAR_COLOR_FG = (0, 255, 0)

# Open video
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"Error: cannot open video '{VIDEO_PATH}'")
    sys.exit(1)

frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
native_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
native_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

# Setup pygame window
screen = pygame.display.set_mode((native_w, native_h), pygame.RESIZABLE)
pygame.display.set_caption(WINDOW_TITLE)
clock = pygame.time.Clock()
font = pygame.font.SysFont(FONT_NAME, FONT_SIZE, bold=False)

# State
current_frame_idx = 0
paused = True
skip = 40
frame = None
ret = False
zoom = 1.0
offset_x = (
    0.0  # offset of the top-left of the scaled video relative to window (in pixels)
)
offset_y = 0.0
panning = False
pan_last_pos = (0, 0)

mouse_pos = (0, 0)
text_surface = None


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def reset_view():
    global zoom, offset_x, offset_y
    zoom = 1.0
    offset_x = 0.0
    offset_y = 0.0


def frame_to_surface(frame_bgr):
    """
    Convert an OpenCV BGR frame to a pygame Surface (RGB).
    Returns the surface and its (w, h).
    """
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w = frame_rgb.shape[:2]
    # pygame expects (width, height) ordering for making surface from array.
    surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    return surf, w, h


def draw_info_overlay(screen, zoom, frame_idx, fps, instructions, mouse_world):
    """
    Draws the top-left overlay with zoom/frame info and instructions.
    """
    padding = 8
    lines = [
        f"Zoom: {zoom:.2f}x",
        f"Frame: {frame_idx}/{frame_count}",
        f"Video FPS: {video_fps:.2f}",
        f"Display FPS: {fps:.1f}",
    ]
    if mouse_world is not None:
        mx, my = mouse_world
        lines.append(f"Cursor (video coords): ({mx}, {my})")
    lines.extend(
        [
            "",
            "Controls: Space Play/Pause | Wheel Zoom | Right-drag Pan | R Reset | Click bar to seek",
        ]
    )

    # Render lines and compute background rect
    rendered = [font.render(line, True, TEXT_COLOR) for line in lines]
    width = max(surf.get_width() for surf in rendered) if rendered else 0
    height = (
        sum(surf.get_height() for surf in rendered)
        + padding * 2
        + (len(rendered) - 1) * 2
    )
    bg_rect = pygame.Rect(10, 10, width + padding * 2, height)
    # Semi-opaque background
    s = pygame.Surface((bg_rect.w, bg_rect.h))
    s.set_alpha(180)
    s.fill((10, 10, 10))
    screen.blit(s, (bg_rect.x, bg_rect.y))

    # Blit text
    y = bg_rect.y + padding
    for surf in rendered:
        screen.blit(surf, (bg_rect.x + padding, y))
        y += surf.get_height() + 2


def get_mouse_world_pos(mouse_x, mouse_y, offset_x, offset_y, zoom):
    """
    Convert a mouse position in window coordinates to video pixel coordinates (world).
    Returns integer (x, y) or None if outside the video bounds.
    """
    world_x = int((mouse_x - offset_x) / zoom)
    world_y = int((mouse_y - offset_y) / zoom)
    if 0 <= world_x < native_w and 0 <= world_y < native_h:
        return world_x, world_y
    return None


# Initially read the first frame
cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
ret, frame = cap.read()
if not ret:
    frame = np.zeros((native_h, native_w, 3), dtype=np.uint8)

running = True
while running:
    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.VIDEORESIZE:
            # Preserve existing window content scaling/panning; only change available window size
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                paused = not paused
            elif (
                event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS
            ):  # + key (shift + =)
                mx, my = pygame.mouse.get_pos()
                pre_world_x = (mx - offset_x) / zoom
                pre_world_y = (my - offset_y) / zoom
                zoom = clamp(zoom * ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)
                offset_x = mx - pre_world_x * zoom
                offset_y = my - pre_world_y * zoom
            elif event.key == pygame.K_MINUS:
                mx, my = pygame.mouse.get_pos()
                pre_world_x = (mx - offset_x) / zoom
                pre_world_y = (my - offset_y) / zoom
                zoom = clamp(zoom / ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)
                offset_x = mx - pre_world_x * zoom
                offset_y = my - pre_world_y * zoom
            elif event.key == pygame.K_r:
                reset_view()
            elif event.key == pygame.K_x:
                if frame is not None:
                    cv2.imwrite("image.png", frame)
                    print("Saved current frame as image.png")
            elif event.key == pygame.K_ESCAPE:
                running = False

        elif event.type == pygame.MOUSEMOTION:
            mouse_pos = event.pos
            if panning:
                # compute delta and apply to offsets
                dx = event.pos[0] - pan_last_pos[0]
                dy = event.pos[1] - pan_last_pos[1]
                offset_x += dx
                offset_y += dy
                pan_last_pos = event.pos
            # update simple hover text
            # (we'll compute the world coord and draw it later)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == PAN_BUTTON:
                panning = True
                pan_last_pos = event.pos
            elif event.button == 1:
                mx, my = event.pos
                if my >= screen.get_height() - BAR_HEIGHT:
                    # Click on progress bar
                    fraction = mx / screen.get_width()
                    new_frame = (
                        int(fraction * (frame_count - 1)) if frame_count > 1 else 0
                    )
                    current_frame_idx = clamp(new_frame, 0, frame_count - 1)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
                    ret, frame = cap.read()
                    if not ret:
                        frame = np.zeros((native_h, native_w, 3), dtype=np.uint8)
                else:
                    mouse_pos = event.pos
            # Support wheel via button 4/5 for older pygame/backends
            elif event.button == 4:  # wheel up
                mx, my = event.pos
                # Zoom towards mouse position
                pre_world_x = (mx - offset_x) / zoom
                pre_world_y = (my - offset_y) / zoom
                zoom = clamp(zoom * ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)
                # update offset so that the pixel under cursor stays under cursor
                offset_x = mx - pre_world_x * zoom
                offset_y = my - pre_world_y * zoom
            elif event.button == 5:  # wheel down
                mx, my = event.pos
                pre_world_x = (mx - offset_x) / zoom
                pre_world_y = (my - offset_y) / zoom
                zoom = clamp(zoom / ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)
                offset_x = mx - pre_world_x * zoom
                offset_y = my - pre_world_y * zoom

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == PAN_BUTTON:
                panning = False

        # New in pygame 2: MOUSEWHEEL event
        if event.type == pygame.MOUSEWHEEL:
            # event.y = 1 for up, -1 for down
            try:
                mx, my = pygame.mouse.get_pos()
            except Exception:
                mx, my = mouse_pos
            pre_world_x = (mx - offset_x) / zoom
            pre_world_y = (my - offset_y) / zoom
            if event.y > 0:
                zoom = clamp(zoom * (ZOOM_STEP**event.y), MIN_ZOOM, MAX_ZOOM)
            else:
                zoom = clamp(zoom / (ZOOM_STEP ** (-event.y)), MIN_ZOOM, MAX_ZOOM)
            offset_x = mx - pre_world_x * zoom
            offset_y = my - pre_world_y * zoom

    keys = pygame.key.get_pressed()
    if keys[pygame.K_RIGHT]:
        current_frame_idx = min(frame_count - 1, current_frame_idx + skip)
        for _ in range(skip - 1):
            cap.read()
        ret, frame = cap.read()
    if keys[pygame.K_LEFT]:
        current_frame_idx = max(0, current_frame_idx - skip)
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
        ret, frame = cap.read()

    # Playback logic
    if not paused:
        current_frame_idx = min(frame_count - 1, current_frame_idx + 1)
        ret, frame = cap.read()
        if not ret:
            # loop or pause at end
            paused = True
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
    else:
        # keep current frame as-is; if user used left/right keys we already set cap
        pass

    # Draw the frame with zoom and pan
    if frame is not None:
        frame_surf, fw, fh = frame_to_surface(frame)
        # Compute scaled size
        scaled_w = max(1, int(fw * zoom))
        scaled_h = max(1, int(fh * zoom))
        scaled_surf = pygame.transform.scale(frame_surf, (scaled_w, scaled_h))
        # try:
        #     scaled_surf = pygame.transform.smoothscale(frame_surf, (scaled_w, scaled_h))
        # except Exception:
        #     # fallback to regular scale if smoothscale fails
        #     scaled_surf = pygame.transform.scale(frame_surf, (scaled_w, scaled_h))

        # Fill background to avoid visual garbage outside the video area
        screen.fill((30, 30, 30))

        # Blit scaled surface at offset (which may be negative or positive)
        screen.blit(scaled_surf, (offset_x, offset_y))

        # Draw mouse hover coordinates in video space (if inside)
        mx, my = pygame.mouse.get_pos()
        mouse_world = get_mouse_world_pos(mx, my, offset_x, offset_y, zoom)
        if mouse_world is not None:
            wx, wy = mouse_world
            coord_surf = font.render(f"({wx}, {wy})", True, (255, 255, 0))
            # Draw a small crosshair at the hovered pixel (in window coords)
            cross_x = offset_x + wx * zoom
            cross_y = offset_y + wy * zoom
            # Only draw crosshair if within window bounds
            if 0 <= cross_x < screen.get_width() and 0 <= cross_y < screen.get_height():
                pygame.draw.line(
                    screen,
                    (255, 200, 0),
                    (cross_x - 8, cross_y),
                    (cross_x + 8, cross_y),
                    1,
                )
                pygame.draw.line(
                    screen,
                    (255, 200, 0),
                    (cross_x, cross_y - 8),
                    (cross_x, cross_y + 8),
                    1,
                )
            screen.blit(
                coord_surf,
                (10, screen.get_height() - BAR_HEIGHT - coord_surf.get_height() - 10),
            )
        else:
            mouse_world = None

        # Draw overlay info
        fps = clock.get_fps()
        draw_info_overlay(screen, zoom, current_frame_idx, fps, None, mouse_world)

        # Draw progress bar
        bar_rect = pygame.Rect(
            0, screen.get_height() - BAR_HEIGHT, screen.get_width(), BAR_HEIGHT
        )
        pygame.draw.rect(screen, BAR_COLOR_BG, bar_rect)
        if frame_count > 1:
            progress_width = int(
                (current_frame_idx / (frame_count - 1)) * screen.get_width()
            )
            progress_rect = pygame.Rect(
                0, screen.get_height() - BAR_HEIGHT, progress_width, BAR_HEIGHT
            )
            pygame.draw.rect(screen, BAR_COLOR_FG, progress_rect)

        pygame.display.flip()

    clock.tick(60)  # cap to 60 FPS for the UI responsiveness

cap.release()
pygame.quit()
