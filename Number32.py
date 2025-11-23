import pygame
import random
import sys

pygame.init()

# Окно
WIDTH, HEIGHT = 600, 500
#screen = pygame.display.set_mode((WIDTH, HEIGHT))
# Флаг NOFRAME убирает рамку с крестиком
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME)
#screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("Figures Demo")

FONT = pygame.font.SysFont(None, 36)

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
COLORS = [(255, 0, 0), (0, 128, 255), (0, 200, 0), (255, 165, 0), (200, 0, 200)]

# --- Функции рисования фигур ---
def draw_circle(x, y, color):
    pygame.draw.circle(screen, color, (x, y), 50)

def draw_square(x, y, color):
    pygame.draw.rect(screen, color, (x-50, y-50, 100, 100))

def draw_triangle(x, y, color):
    points = [(x, y-60), (x-55, y+40), (x+55, y+40)]
    pygame.draw.polygon(screen, color, points)

def draw_hexagon(x, y, color):
    r = 50
    points = [
        (x + r, y),
        (x + r/2, y + int(r*0.87)),
        (x - r/2, y + int(r*0.87)),
        (x - r, y),
        (x - r/2, y - int(r*0.87)),
        (x + r/2, y - int(r*0.87))
    ]
    pygame.draw.polygon(screen, color, points)

def draw_cross(x, y, color):
    pygame.draw.rect(screen, color, (x - 15, y - 60, 30, 120))
    pygame.draw.rect(screen, color, (x - 60, y - 15, 120, 30))


# Все фигуры
shapes = [
    draw_circle,
    draw_square,
    draw_triangle,
    draw_hexagon,
    draw_cross
]

# --- Кнопка ---
button_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT - 80, 200, 50)

def draw_button():
    pygame.draw.rect(screen, (220, 220, 220), button_rect)
    pygame.draw.rect(screen, BLACK, button_rect, 2)
    text = FONT.render("Обновить", True, BLACK)
    screen.blit(text, (button_rect.x + 35, button_rect.y + 10))


def get_new_objects():
    selected_shapes = random.sample(shapes, 2)

    # Выбираем 2 разных цвета
    color1, color2 = random.sample(COLORS, 2)

    selected_colors = [color1, color2]
    return selected_shapes, selected_colors


current_shapes, current_colors = get_new_objects()

# --- Главный цикл ---
running = True
while running:
    screen.fill(WHITE)

    # Рисуем фигуры со СТАБИЛЬНЫМИ цветами
    current_shapes[0](WIDTH//3, HEIGHT//2 - 50, current_colors[0])
    current_shapes[1](2*WIDTH//3, HEIGHT//2 - 50, current_colors[1])

    # Кнопка
    draw_button()

    # События
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if button_rect.collidepoint(event.pos):
                current_shapes, current_colors = get_new_objects()

    pygame.display.flip()

pygame.quit()
sys.exit()

