import pygame
import random
import sys
from multiprocessing import Process, Pipe
import os
import subprocess
import time

# -------------------- Настройки расположения окон --------------------
HDMI1_POS = "800,0"
HDMI2_POS = "1824,0"
HDMI_SIZE = (1024, 600)
SPLASH_PATH = "/home/game/gamepi/1.png"
# --------------------------------------------------------------------

FIGURE_DEFS = {
    "circle":   ((255, 165, 0), "circle"),
    "hexagon":  ((200, 0, 200), "hexagon"),
    "triangle": ((0, 200, 0), "triangle"),
    "cross":    ((0, 128, 255), "cross"),
    "square":   ((255, 0, 0), "square")
}
FIGURE_ORDER = list(FIGURE_DEFS.keys())
NATURAL_COLORS = {f: FIGURE_DEFS[f][0] for f in FIGURE_ORDER}

# ---------------- drawing funcs ----------------
def draw_circle(screen, x, y, color):
    pygame.draw.circle(screen, color, (x, y), 160)

def draw_square(screen, x, y, color):
    pygame.draw.rect(screen, color, (x - 160, y - 160, 320, 320))

def draw_triangle(screen, x, y, color):
    points = [(x, y-200), (x-180, y+160), (x+180, y+160)]
    pygame.draw.polygon(screen, color, points)

def draw_hexagon(screen, x, y, color):
    r = 180
    points = [
        (x + r, y),
        (x + r/2, y + int(r*0.87)),
        (x - r/2, y + int(r*0.87)),
        (x - r, y),
        (x - r/2, y - int(r*0.87)),
        (x + r/2, y - int(r*0.87))
    ]
    pygame.draw.polygon(screen, color, points)

def draw_cross(screen, x, y, color):
    pygame.draw.rect(screen, color, (x - 50, y - 160, 100, 320))
    pygame.draw.rect(screen, color, (x - 160, y - 50, 320, 100))

DRAW_FUNCS = {
    "circle": draw_circle,
    "square": draw_square,
    "triangle": draw_triangle,
    "hexagon": draw_hexagon,
    "cross": draw_cross
}

def generate_two_wrong():
    shapes = random.sample(FIGURE_ORDER, 2)
    result = []
    used_colors = set()
    for sh in shapes:
        natural = NATURAL_COLORS[sh]
        wrong_colors = [c for c in NATURAL_COLORS.values() if c != natural]
        available = [c for c in wrong_colors if c not in used_colors]
        color = random.choice(available)
        used_colors.add(color)
        result.append((sh, color))
    return result

# ---------------- HDMI window (HDMI1 & HDMI2) ----------------
def hdmi_window(conn, pos):
    os.environ['SDL_VIDEO_WINDOW_POS'] = pos
    pygame.init()
    screen = pygame.display.set_mode(HDMI_SIZE, pygame.NOFRAME)
    pygame.display.set_caption("HDMI (mirror)")
    clock = pygame.time.Clock()

    # загрузка заставки
    splash_img = None
    try:
        splash_img = pygame.image.load(SPLASH_PATH)
    except Exception as e:
        print("HDMI: не удалось загрузить заставку:", e)

    mode = "splash"  # "splash" или "game"
    figures = generate_two_wrong()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # обработка входящих сообщений
        while conn.poll():
            msg = conn.recv()
            # msg может быть:
            # ('mode', 'splash'/'game'), ('figures', figures), 'quit'
            if msg == "quit":
                running = False
            elif isinstance(msg, tuple) and msg[0] == "mode":
                mode = msg[1]
            elif isinstance(msg, tuple) and msg[0] == "figures":
                figures = msg[1]
            elif isinstance(msg, list):
                # совместимость со старым кодом: если пришли просто figures
                figures = msg

        screen.fill((255, 255, 255))

        if mode == "splash":
            if splash_img:
                # масштабируем под окно
                img = pygame.transform.smoothscale(splash_img, screen.get_size())
                screen.blit(img, (0, 0))
            else:
                # если нет картинки, простой текст
                font = pygame.font.SysFont(None, 48)
                screen.blit(font.render("SPLASH (no image)", True, (0,0,0)), (50,50))
        else:
            # режим игры — рисуем фигуры
            for i, (shape, color) in enumerate(figures):
                func = DRAW_FUNCS[shape]
                x = HDMI_SIZE[0] // 3 - 50 if i == 0 else 2 * HDMI_SIZE[0] // 3 + 50
                func(screen, x, 300, color)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

# ---------------- DSI window (fullscreen, отвечает за старт) ----------------
def dsi_window(conn):
    os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("DSI")
    clock = pygame.time.Clock()

    # fonts
    cpu_font = pygame.font.SysFont(None, 36)
    FONT = pygame.font.SysFont(None, 48)

    # load splash
    splash_img = None
    try:
        splash_img = pygame.image.load(SPLASH_PATH)
    except Exception as e:
        print("DSI: не удалось загрузить заставку:", e)

    # кнопка обновления — невидимая зона нижних 2/3
    button_rect = pygame.Rect(
        0,
        screen.get_height() // 3,
        screen.get_width(),
        screen.get_height() * 2 // 3
    )
    # shutdown button (маленькая)
    shutdown_rect = pygame.Rect(20, 20, 110, 40)

    mode = "splash"  # splash или game
    figures = generate_two_wrong()

    # получить начальные данные (на всякий случай)
    try:
        if conn.poll(timeout=0.1):
            init_msg = conn.recv()
            if isinstance(init_msg, tuple) and init_msg[0] == "figures":
                figures = init_msg[1]
            elif isinstance(init_msg, list):
                figures = init_msg
            elif isinstance(init_msg, tuple) and init_msg[0] == "mode":
                mode = init_msg[1]
    except Exception:
        pass

    # вспомогательная функция для выбора правильной фигуры
    def compute_correct(figs):
        used_shapes = {shape for shape, _ in figs}
        used_colors = {tuple(color) for _, color in figs}
        for sh in FIGURE_ORDER:
            nat_color = tuple(NATURAL_COLORS[sh])
            if sh not in used_shapes and nat_color not in used_colors:
                return sh, NATURAL_COLORS[sh]
        for sh in FIGURE_ORDER:
            if sh not in used_shapes:
                return sh, NATURAL_COLORS[sh]
        return FIGURE_ORDER[0], NATURAL_COLORS[FIGURE_ORDER[0]]

    correct = compute_correct(figures)
    cpu_temp = "CPU: --°C"
    next_temp_time = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                # если в режиме заставки — любой клик запускает игру
                if mode == "splash":
                    # отправляем команду start в main
                    try:
                        conn.send("start")
                    except Exception:
                        pass
                    # переключаемся локально в game (чтобы не ждать лишний раунд)
                    mode = "game"
                else:
                    # когда в режиме игры — клик в невидимую зону запускает refresh
                    if button_rect.collidepoint(event.pos):
                        try:
                            conn.send("refresh")
                        except Exception:
                            pass
                        # ждём ответ (новые фигуры)
                        if conn.poll(timeout=5):
                            msg = conn.recv()
                            if isinstance(msg, list):
                                figures = msg
                                correct = compute_correct(figures)
                            elif isinstance(msg, tuple) and msg[0] == "figures":
                                figures = msg[1]
                                correct = compute_correct(figures)
                        else:
                            pass

                # shutdown
                if shutdown_rect.collidepoint(event.pos):
                    pygame.quit()
                    subprocess.call(["sudo", "shutdown", "-h", "now"])
                    sys.exit()

        # обработка входящих сообщений (main -> dsi)
        while conn.poll():
            msg = conn.recv()
            if msg == "quit":
                running = False
            elif isinstance(msg, tuple) and msg[0] == "mode":
                mode = msg[1]
            elif isinstance(msg, tuple) and msg[0] == "figures":
                figures = msg[1]
                correct = compute_correct(figures)
            elif isinstance(msg, list):
                figures = msg
                correct = compute_correct(figures)

        screen.fill((255, 255, 255))

        if mode == "splash":
            if splash_img:
                img = pygame.transform.smoothscale(splash_img, screen.get_size())
                screen.blit(img, (0, 0))
            else:
                screen.blit(FONT.render("SPLASH (no image)", True, (0,0,0)), (50,50))
            # подсказка
            hint = pygame.font.SysFont(None, 28).render("СТАРТ", True, (0,0,0))
            screen.blit(hint, (screen.get_width()//2 - hint.get_width()//2, screen.get_height() - 80))
        else:
            # рисуем правильную фигуру
            func = DRAW_FUNCS[correct[0]]
            func(screen, screen.get_width() // 2, 220, correct[1])

            # кнопка выключения
            pygame.draw.rect(screen, (255, 0, 0), shutdown_rect)
            pygame.draw.rect(screen, (0, 0, 0), shutdown_rect, 3)
            screen.blit(pygame.font.SysFont(None, 24).render("SHUTDOWN", True, (255, 255, 255)),
                        (shutdown_rect.x + 5, shutdown_rect.y + 15))

        # обновление температуры раз в 5 сек
        if time.time() >= next_temp_time:
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    t = int(f.read()) / 1000
                cpu_temp = f"{t:.1f}°C"
            except:
                cpu_temp = "--°C"
            next_temp_time = time.time() + 5

        text_surface = cpu_font.render(cpu_temp, True, (0, 0, 0))
        screen.blit(text_surface, (screen.get_width() - text_surface.get_width() - 20, 20))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    # pipes
    main_h1_parent, h1_child = Pipe()
    main_h2_parent, h2_child = Pipe()
    main_dsi_parent, dsi_child = Pipe()

    # processes
    p_hdmi1 = Process(target=hdmi_window, args=(h1_child, HDMI1_POS), daemon=True)
    p_hdmi2 = Process(target=hdmi_window, args=(h2_child, HDMI2_POS), daemon=True)
    p_dsi = Process(target=dsi_window, args=(dsi_child,), daemon=True)

    p_hdmi1.start()
    p_hdmi2.start()
    p_dsi.start()

    # initial mode = splash
    mode = "splash"
    figures = generate_two_wrong()

    # отправляем режим splash всем
    try:
        main_h1_parent.send(("mode", "splash"))
        main_h2_parent.send(("mode", "splash"))
        main_dsi_parent.send(("mode", "splash"))
    except Exception:
        pass

    # также можно отправить начальные фигуры (необязательно при splash)
    try:
        main_h1_parent.send(("figures", figures))
        main_h2_parent.send(("figures", figures))
        main_dsi_parent.send(("figures", figures))
    except Exception:
        pass

    try:
        while True:
            # DSI может прислать "start" или "refresh"
            if main_dsi_parent.poll():
                msg = main_dsi_parent.recv()
                if msg == "refresh":
                    figures = generate_two_wrong()
                    # разослать всем новые фигуры (и DSI тоже)
                    try:
                        main_h1_parent.send(("figures", figures))
                        main_h2_parent.send(("figures", figures))
                        main_dsi_parent.send(("figures", figures))
                    except Exception:
                        pass
                elif msg == "start":
                    # переключаем все окна в game
                    mode = "game"
                    try:
                        main_h1_parent.send(("mode", "game"))
                        main_h2_parent.send(("mode", "game"))
                        main_dsi_parent.send(("mode", "game"))
                        # и отправляем текущие фигуры
                        main_h1_parent.send(("figures", figures))
                        main_h2_parent.send(("figures", figures))
                        main_dsi_parent.send(("figures", figures))
                    except Exception:
                        pass
                # если main получает другие команды - можно расширить
            time.sleep(0.05)
    except KeyboardInterrupt:
        try:
            main_h1_parent.send("quit")
        except Exception:
            pass
        try:
            main_h2_parent.send("quit")
        except Exception:
            pass
        try:
            main_dsi_parent.send("quit")
        except Exception:
            pass

        p_hdmi1.join(timeout=1)
        p_hdmi2.join(timeout=1)
        p_dsi.join(timeout=1)
        sys.exit(0)

