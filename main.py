# ------------------------------------------------------- #
# Blastar Remastered                                      #
#   by: Sid and Krish                                     #
#                                                         #
# "If I had gone to the point of adding velocity maybe    #
#   I should've included a whole physics engine as well"  #
#                       -I, who regrets everything, 2021  #
#                                                         #
# "That's right I waited to 2021 to actually start        #
#   seriously cracking down on this project."             #
#             -I, who didn't really regret that one, 2021 #
#                                                         #
# "Probably should've written tests."                     #
#                                                         #
# Credits to my mother for math support                   #
# ------------------------------------------------------- #

# Note: This game is best played natively

import random
import socket
import sys
import threading

import pygame
from pygame.locals import *

from core import *


class GenericController():
    def __init__(self):
        # ? Settings (I know somebody's gonna change something in here and cheat D:<)
        self.scrDimensions = (800, 800)

        self.targetFPS = 144

        self.gameSpeedFactor = 1000

        self.deathFrames = round(self.targetFPS * 0.5, 0)
        self.speed = 0.6
        self.maxSpeed = 5
        self.falloff = 0.1

        # ? Init

        pygame.init()

        self.screen = pygame.display.set_mode(self.scrDimensions)

        self.game = Game(self.screen, [], self.deathFrames)

    def run(self):
        self.player = SpaceObject(
            pos=[random.randint(20, self.scrDimensions[0] - 20),
                 random.randint(20, self.scrDimensions[1] - 20)],
            scr=self.screen,
            sprite=pygame.image.load("player.png"),
            dead=pygame.image.load("player_death.png"),
            maxVelSpeed=self.maxSpeed,
            onWallCollided=self.limitPlayers,
            onCollision=self.onAllCollided,
            givenID="Player",
            velocityFalloff=self.falloff
        )

        self.game.summon(self.player)

        # ? Some text rendering stuff
        WHITE = (255, 255, 255)
        BLACK = (0, 0, 0)

        fontsize = 20
        font = pygame.font.SysFont(None, fontsize)
        w, h = self.screen.get_size()

        self.clock = pygame.time.Clock()

        while True:
            self.clock.tick(self.targetFPS)

            self.fps = self.clock.get_fps()
            if self.fps == 0:
                self.fps = 1

            keystate = pygame.key.get_pressed()

            if keystate[pygame.K_LEFT]:
                self.player.velocity.x = -self.speed * \
                    (self.gameSpeedFactor / self.fps)
            if keystate[pygame.K_RIGHT]:
                self.player.velocity.x = self.speed * \
                    (self.gameSpeedFactor / self.fps)
            if keystate[pygame.K_UP]:
                self.player.velocity.y = -self.speed * \
                    (self.gameSpeedFactor / self.fps)
            if keystate[pygame.K_DOWN]:
                self.player.velocity.y = self.speed * \
                    (self.gameSpeedFactor / self.fps)
            if keystate[pygame.K_SPACE]:  # ? Shoot
                # * This is not a great solution especially for lower frame rates however it will do for now
                if self.game.frame % round(self.targetFPS * 0.15, 0) == 0 and self.player.isDead == False:
                    self.game.summon(SpaceObject(
                        pos=self.player.pos,
                        scr=self.screen,
                        sprite=pygame.image.load("player_bullet.png"),
                        dead=pygame.Surface((0, 0)),
                        maxVelSpeed=6,
                        onWallCollided=self.limitBullet,
                        onCollision=self.onAllCollided,
                        givenID="Player_Bullet",
                        velocityFalloff=self.falloff,
                        initVelocity=Velocity(0, -6, 0, True, 6)
                    ))
            if keystate[pygame.K_ESCAPE]:
                pygame.quit()
                sys.exit()

            # ? Some text overlays
            img = font.render(str(self.player.velocity), True, BLACK)
            self.screen.blit(img, (5, h))

            img = font.render(str(int(self.fps)), True, BLACK)
            self.screen.blit(img, (5, 0))

            self.game.tick()

            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()

            pygame.display.update()
            self.screen.fill(WHITE)

    def limitPlayers(self, obj):
        obj.pos[0] = clamp(obj.pos[0], 0, self.scrDimensions[0])
        obj.pos[1] = clamp(obj.pos[1], 0, self.scrDimensions[1])

    def onAllCollided(self, obj, target):
        if obj.id.split("_")[0] not in target.id and target.id.split("_")[0] not in obj.id:
            self.game.kill(obj, target)

    def limitBullet(self, obj):
        if (obj.pos[0] <= 0 or obj.pos[0] >= self.scrDimensions[0]) or (obj.pos[1] <= 0 or obj.pos[1] >= self.scrDimensions[1]):
            self.game.kill(obj)


class SingleplayerController(GenericController):
    def __init__(self):
        super().__init__()
        self.game.summon(SpaceObject(
            pos=[random.randint(20, self.scrDimensions[0] - 20),
                 random.randint(20, self.scrDimensions[1] - 20)],
            scr=self.screen,
            sprite=pygame.image.load("enemy.png"),
            dead=pygame.image.load("enemy_death.png"),
            maxVelSpeed=self.maxSpeed,
            onWallCollided=self.limitPlayers,
            onCollision=self.onAllCollided,
            givenID="Enemy",
            velocityFalloff=self.falloff
        ))


# ? Network Protcol Packet Types:
# ? -----------------------------------
# ? 0: Player Join
# ? 1: Player Movement
# ? 2: Velocity Sync
# ? 3: Player Shoot
# ? 4: Player Quit

class NetworkController(GenericController):
    def __init__(self):
        super().__init__()

    def summonPlayer(self):
        self.player = SpaceObject(
            pos=[random.randint(20, self.scrDimensions[0] - 20),
                 random.randint(20, self.scrDimensions[1] - 20)],
            scr=self.screen,
            sprite=pygame.image.load("player.png"),
            dead=pygame.image.load("player_death.png"),
            maxVelSpeed=self.maxSpeed,
            onWallCollided=self.limitPlayers,
            onCollision=self.onAllCollided,
            givenID="Player",
            velocityFalloff=self.falloff
        )
        self.game.summon(self.player)
        # ? Packet Type 0: Player Join
        self.client.sendto(b"\x00" + self.player.toBytes(), self.remoteAddr)

    def run(self, addr: str, port: int):
        self.remoteAddr = (addr, port)

        self.opponents = {}

        self.syncThresh = 0.1
        self.synced = True

        self.opponentSprite = pygame.image.load("enemy.png")
        self.opponentDead = pygame.image.load("enemy_death.png")

        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.summonPlayer()

        self.recvThread = threading.Thread(
            target=self.packetHandler, daemon=True)
        self.recvThread.start()

        WHITE = (255, 255, 255)
        BLACK = (0, 0, 0)

        fontsize = 20
        font = pygame.font.SysFont(None, fontsize)
        w, h = self.screen.get_size()

        self.clock = pygame.time.Clock()

        while True:
            self.clock.tick(self.targetFPS)

            self.fps = self.clock.get_fps()
            if self.fps == 0:
                self.fps = 1

            keystate = pygame.key.get_pressed()

            # ? Player Movement Direction Protocol Description (Packet Type 1)
            # ? [1 Byte (Movement Type)]

            if keystate[pygame.K_LEFT]:  # ? Movement Type 0
                self.player.velocity.x = -self.speed * \
                    (self.gameSpeedFactor / self.fps)
                self.client.sendto(b"\x01\x00", self.remoteAddr)
                self.synced = False
            if keystate[pygame.K_RIGHT]:  # ? Movement Type 1
                self.player.velocity.x = self.speed * \
                    (self.gameSpeedFactor / self.fps)
                self.client.sendto(b"\x01\x01", self.remoteAddr)
                self.synced = False
            if keystate[pygame.K_UP]:  # ? Movement Type 2
                self.player.velocity.y = -self.speed * \
                    (self.gameSpeedFactor / self.fps)
                self.client.sendto(b"\x01\x02", self.remoteAddr)
                self.synced = False
            if keystate[pygame.K_DOWN]:  # ? Movement Type 3
                self.player.velocity.y = self.speed * \
                    (self.gameSpeedFactor / self.fps)
                self.client.sendto(b"\x01\x03", self.remoteAddr)
                self.synced = False
            if keystate[pygame.K_SPACE]:  # ? Shoot
                # * This is not a great solution especially for lower frame rates however it will do for now
                if self.game.frame % round(self.targetFPS * 0.15, 0) == 0 and self.player.isDead == False:
                    self.game.summon(SpaceObject(
                        pos=self.player.pos,
                        scr=self.screen,
                        sprite=pygame.image.load("player_bullet.png"),
                        dead=pygame.Surface((0, 0)),
                        maxVelSpeed=6,
                        onWallCollided=self.limitBullet,
                        onCollision=self.onAllCollided,
                        givenID="Player_Bullet",
                        velocityFalloff=self.falloff,
                        initVelocity=Velocity(0, -6, 0, True, 6)
                    ))
                    self.client.sendto(b"\x03", self.remoteAddr)
            if keystate[pygame.K_r]: #? Respawn
                if self.player.isDead == True:
                    self.summonPlayer()
            if keystate[pygame.K_ESCAPE]:
                # ? Packet type 4: Quit
                self.quit()

            if abs(self.player.velocity.x) < self.syncThresh and abs(self.player.velocity.y) < self.syncThresh and self.synced != True:  # ? Packet type 2: Sync
                self.client.sendto(
                    b"\x02" + constructSyncBytes(self.player.pos), self.remoteAddr)
                if self.player.velocity.x == 0 and self.player.velocity.y == 0:
                    self.synced = True
            # ? Some text overlays
            img = font.render(str(self.player.velocity), True, BLACK)
            self.screen.blit(img, (5, h))

            img = font.render(str(int(self.fps)), True, BLACK)
            self.screen.blit(img, (5, 0))

            self.game.tick()

            for event in pygame.event.get():
                if event.type == QUIT:
                    # ? Packet type 5: Quit
                    self.quit()

            pygame.display.update()
            self.screen.fill(WHITE)

    def packetHandler(self):
        while True:
            b, addr = self.client.recvfrom(256)
            if b[1] == 0:  # ? Handle Player Join
                print(b)
                # * For some reason, even though the buffer used by all the types of packets are the same, defining that buffer outside the if statement breaks the interpretation
                buff = b[2:]
                if self.opponents.get(b[0]) == None or self.opponents.get(b[0]).isDead == True:
                    self.client.sendto(
                        b"\x00" + self.player.toBytes(), self.remoteAddr)
                    self.opponents[b[0]] = spaceObjectFromBytes(
                        buff, self.screen, self.opponentSprite, self.opponentDead, self.limitPlayers, self.onAllCollided, f"Enemy_{b[0]}")
                    self.game.summon(self.opponents[b[0]])
            elif b[1] == 1:  # ? Handle Velocity
                buff = b[2]
                if buff == 0:
                    self.opponents[b[0]].velocity.x = -self.speed * \
                        (self.gameSpeedFactor / self.fps)
                elif buff == 1:
                    self.opponents[b[0]].velocity.x = self.speed * \
                        (self.gameSpeedFactor / self.fps)
                elif buff == 2:
                    self.opponents[b[0]].velocity.y = -self.speed * \
                        (self.gameSpeedFactor / self.fps)
                elif buff == 3:
                    self.opponents[b[0]].velocity.y = self.speed * \
                        (self.gameSpeedFactor / self.fps)
            elif b[1] == 2:  # ? Handle Sync
                buff = b[2:]
                syncParams = interpretSyncBytes(buff)
                distX = syncParams[0] - self.opponents[b[0]].pos[0]
                distY = syncParams[1] - self.opponents[b[0]].pos[1]
                a = self.falloff  # ? De-acceleration
                t = 5  # ? Time

                sx = (distX + 1/2 * a * t**2)/t  # ? Speed X (Velocity X)
                sy = (distY + 1/2 * a * t**2)/t  # ? Speed Y (Velocity Y)

                self.opponents[b[0]].velocity.x = sx
                self.opponents[b[0]].velocity.y = sy
            elif b[1] == 3:  # ? Handle shoot
                if self.opponents[b[0]].isDead == False:
                    self.game.summon(SpaceObject(
                        pos=self.opponents[b[0]].pos,
                        scr=self.screen,
                        sprite=pygame.image.load("enemy_bullet.png"),
                        dead=pygame.Surface((0, 0)),
                        maxVelSpeed=6,
                        onWallCollided=self.limitBullet,
                        onCollision=self.onAllCollided,
                        givenID="Enemy_Bullet",
                        velocityFalloff=self.falloff,
                        initVelocity=Velocity(0, -6, 0, True, 6)
                    ))
            elif b[1] == 4:  # ? Handle Quit
                opp = self.opponents.get(b[0])
                if opp != None:
                    self.game.kill(opp)
            else:
                break

    # ? Packet type 4: Player Quit
    def quit(self):
        self.client.sendto(b"\x04", self.remoteAddr)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    menu = open("menu.txt", "r")
    print(menu.read())
    mode = int(input(" > "))
    if mode == 0:
        game = SingleplayerController()
        game.run()
    elif mode == 1:
        print("Specify Multiplayer Server Address")
        addr = input(" > ")
        print("Specify Multiplayer Server Port")
        port = int(input(" > "))

        game = NetworkController()
        game.run(addr, port)
