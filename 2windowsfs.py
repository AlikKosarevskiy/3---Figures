import pygame
import sys
from multiprocessing import Process
import os

# --- Окно на DSI с кругом ---
def dsi_window():
    pygame.init()
    os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"  # начало DSI
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("DSI - Круг")
    
    running = True
    while running:
        screen.fill((255, 255, 255))
        width, height = screen.get_size()
        pygame.draw.circle(screen, (255, 0, 0), (width//2, height//2), 100)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        pygame.display.flip()
    pygame.quit()
    sys.exit()

# --- Окно на HDMI с квадратом ---
def hdmi_window():
    pygame.init()
    os.environ['SDL_VIDEO_WINDOW_POS'] = "800,0"  # смещение на HDMI
#   screen = pygame.display.set_mode((0, 0), pygame.NOFRAME)
    screen = pygame.display.set_mode((1024, 600), pygame.NOFRAME)
    pygame.display.set_caption("HDMI - Квадрат")
    
    running = True
    while running:
        screen.fill((255, 255, 255))
        width, height = screen.get_size()
        pygame.draw.rect(screen, (0, 0, 255), (width//2 - 100, height//2 - 100, 200, 200))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        pygame.display.flip()
    pygame.quit()
    sys.exit()

# --- Главный процесс ---
if __name__ == '__main__':
    p1 = Process(target=dsi_window)
    p2 = Process(target=hdmi_window)
    
    p1.start()
    p2.start()
    
    p1.join()
    p2.join()
