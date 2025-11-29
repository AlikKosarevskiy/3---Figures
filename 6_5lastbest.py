import pygame
import random
import sys
from multiprocessing import Process, Pipe
import os
import subprocess
import time

# -------------------- Настройки расположения окон (подгоняй при необходимости) --------------------
# Позиции в формате "X,Y" для SDL_VIDEO_WINDOW_POS — меняй в зависимости от расположения мониторов.
# Пример: DSI — (0,0) fullscreen, HDMI1 может быть справа (например 800,0), HDMI2 правее HDMI1.
HDMI1_POS = "800,0"
HDMI2_POS = "1840,0"   # подогнать под разрешение и отступ между мониторами
HDMI_SIZE = (1024, 600)  # размер окна HDMI (используется для NOFRAME окон)
# -------------------------------------------------------------------------------------------------

# ----------------------------------------------------------
#  НАБОР — фигура + её родной цвет
# ----------------------------------------------------------
FIGURE_DEFS = {
    "circle":   ((255, 165, 0), "circle"),     # оранжевый
    "hexagon":  ((200, 0, 200), "hexagon"),    # фиолетовый
    "triangle": ((0, 200, 0), "triangle"),     # зелёный
    "cross":    ((0, 128, 255), "cross"),      # синий
    "square":   ((255, 0, 0), "square")        # красный
}

FIGURE_ORDER = list(FIGURE_DEFS.keys())
NATURAL_COLORS = {f: FIGURE_DEFS[f][0] for f in FIGURE_ORDER}


# ----------------------------------------------------------
#                 ФУНКЦИИ РИСОВАНИЯ
# ----------------------------------------------------------
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


# ----------------------------------------------------------
#    ГЕНЕРАЦИЯ ДВУХ НЕПРАВИЛЬНЫХ ФИГУР (общая, у main)
# ----------------------------------------------------------
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


# ----------------------------------------------------------
#                 HDMI процесс (одинаков для HDMI1 и HDMI2)
#                  принимает figures через conn.recv() и ждёт обновлений
# ----------------------------------------------------------
def hdmi_window(conn, pos):
    # pos — строка "X,Y" для позиционирования окна
    os.environ['SDL_VIDEO_WINDOW_POS'] = pos
    pygame.init()
    screen = pygame.display.set_mode(HDMI_SIZE, pygame.NOFRAME)
    pygame.display.set_caption("HDMI (mirror)")

    # сначала получаем фигуры от main
    try:
        figures = conn.recv()
    except EOFError:
        figures = generate_two_wrong()

    running = True
    while running:
        screen.fill((255, 255, 255))

        for i, (shape, color) in enumerate(figures):
            func = DRAW_FUNCS[shape]
            x = HDMI_SIZE[0] // 3 - 50 if i == 0 else 2 * HDMI_SIZE[0] // 3 + 50
            func(screen, x, 300, color)

        # проверяем, не пришло ли обновление
        if conn.poll():
            msg = conn.recv()
            # ожидаем список фигур
            if isinstance(msg, list):
                figures = msg
            # можно поддерживать другие команды при необходимости
            elif msg == "quit":
                running = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        pygame.display.flip()
        pygame.time.delay(10)

    pygame.quit()
    sys.exit()


# ----------------------------------------------------------
#            DSI процесс  (кнопка + правильная фигура)
#            посылает запросы "refresh" в main через conn
# ----------------------------------------------------------
def dsi_window(conn):
    os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("DSI")
    
    # ---------- температура CPU ----------
    cpu_font = pygame.font.SysFont(None, 36)
    cpu_temp = "CPU: --°C"
    next_temp_time = 0
    
    FONT = pygame.font.SysFont(None, 48)

    # КНОПКА ОБНОВИТЬ — невидимая зона нижних 2/3 экрана
    button_rect = pygame.Rect(
        0,
        screen.get_height() // 3,
        screen.get_width(),
        screen.get_height() * 2 // 3
    )

    # кнопка выключения
    shutdown_rect = pygame.Rect(20, 20, 110, 40)

    # получаем начальные фигуры от main
    try:
        figures = conn.recv()
    except EOFError:
        figures = generate_two_wrong()

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

    running = True
    while running:
        screen.fill((255, 255, 255))

        # рисуем правильную фигуру
        func = DRAW_FUNCS[correct[0]]
        func(screen, screen.get_width() // 2, 220, correct[1])

        # невидимая зона обновления (ничего не рисуем)
        # кнопка выключения
        pygame.draw.rect(screen, (255, 0, 0), shutdown_rect)
        pygame.draw.rect(screen, (0, 0, 0), shutdown_rect, 3)
        screen.blit(pygame.font.SysFont(None, 24).render("SHUTDOWN", True, (255, 255, 255)),
                    (shutdown_rect.x + 5, shutdown_rect.y + 15))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                # ОБНОВИТЬ — нажали в невидимой зоне
                if button_rect.collidepoint(event.pos):
                    # шлём запрос в main — main сгенерирует новые фигуры и пошлёт обратно
                    conn.send("refresh")

                    # ждём ответ (новые фигуры) от main
                    # (main в ответ пришлёт тот же объект figures для DSI)
                    if conn.poll(timeout=5):
                        msg = conn.recv()
                        if isinstance(msg, list):
                            figures = msg
                            correct = compute_correct(figures)
                    else:
                        # таймаут — ничего не делаем
                        pass

                # SHUTDOWN
                if shutdown_rect.collidepoint(event.pos):
                    pygame.quit()
                    subprocess.call(["sudo", "shutdown", "-h", "now"])
                    sys.exit()

        # ======= ОБНОВЛЕНИЕ ТЕМПЕРАТУРЫ =======
        if time.time() >= next_temp_time:
            try:
                with open("/sys/class/thermal/thermal_zone0/temp") as f:
                    t = int(f.read()) / 1000
                cpu_temp = f"{t:.1f}°C"
            except:
                cpu_temp = "--°C"

            next_temp_time = time.time() + 5  # обновление раз в 5 сек

# вывод температуры в правом верхнем углу
        text_surface = cpu_font.render(cpu_temp, True, (0, 0, 0))
        screen.blit(text_surface, (screen.get_width() - text_surface.get_width() - 20, 20))


        pygame.display.flip()
        pygame.time.delay(10)

    pygame.quit()
    sys.exit()


# ----------------------------------------------------------
#                   MAIN PROCESS (координирует обмен)
# ----------------------------------------------------------
if __name__ == "__main__":
    # Pipe между main <-> hdmi1
    main_h1_parent, h1_child = Pipe()
    # Pipe между main <-> hdmi2
    main_h2_parent, h2_child = Pipe()
    # Pipe между main <-> dsi
    main_dsi_parent, dsi_child = Pipe()

    # создаём процессы, передаём им "детскую" сторону их pipe
    p_hdmi1 = Process(target=hdmi_window, args=(h1_child, HDMI1_POS), daemon=True)
    p_hdmi2 = Process(target=hdmi_window, args=(h2_child, HDMI2_POS), daemon=True)
    p_dsi = Process(target=dsi_window, args=(dsi_child,), daemon=True)

    # стартуем процессы
    p_hdmi1.start()
    p_hdmi2.start()
    p_dsi.start()

    # main генерирует начальные фигуры и рассылает всем трём
    figures = generate_two_wrong()
    # отправляем список фигур (двух неправильных) hdmi1, hdmi2 и DSI
    main_h1_parent.send(figures)
    main_h2_parent.send(figures)
    main_dsi_parent.send(figures)

    try:
        # основной цикл: ждём команд от DSI (refresh)
        while True:
            # проверяем, не пришёл ли запрос от DSI
            if main_dsi_parent.poll():
                msg = main_dsi_parent.recv()
                if msg == "refresh":
                    # сгенерировать новые фигуры и разослать их всем трём
                    figures = generate_two_wrong()
                    main_h1_parent.send(figures)
                    main_h2_parent.send(figures)
                    main_dsi_parent.send(figures)
            # небольшой sleep, чтобы цикл не грузил CPU
            time.sleep(0.05)
    except KeyboardInterrupt:
        # корректный выход при ctrl+c, остановим процессы
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

