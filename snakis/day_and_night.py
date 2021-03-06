import numpy as np
import pygame
from math import *
import colorsys
import threading
import queue
import time
import random

class SimpleThread(threading.Thread):
    def __init__(self, func):
        threading.Thread.__init__(self)
        self._func = func
        self.daemon = True
    def run(self):
        self._func()

class DayAndNight:
        
    data_type = "diffuse normal specular emissive team".split()
    shape_type = "straight corner head tail".split()
    rotate = [60 * i for i in range(6)]

    def __init__(self, filename_format, player_colors):
        self._player_colors = player_colors
        self._snake_images = None
        player_count = len(player_colors)
        self._image_factory = [None] * player_count
        self._filename_format = filename_format
        self._daytime = None

        self._task_queue = queue.Queue(player_count)
        
        # master sits on a chair and manages his slaves
        SimpleThread(self.loadAsyncMaster).start()
        
        # slaves obey to their master and work hard
        for i in range(player_count):
            SimpleThread(self.loadAsyncSlave).start()

    def updateLight(self):
        day_duration = 24
        if self._daytime is None:
            self._light = {}
            self._daytime = random.randint(0, day_duration-1)
        else:
            self._daytime = (self._daytime+0.25) % day_duration
        print("Time:",self._daytime, '/', day_duration)
        t = self._daytime / day_duration

        colors = np.matrix([
            [150, 220, 255], # night blue
            [150, 220, 255], # night blue
            [255, 170, 180],  # pink sunrise
            [255, 220, 150],   # orange
            [255, 246, 186],    # yellow
            [255, 255, 255],    # bright yellow
            [255, 255, 255],    # bright yellow
            [255, 246, 186],    # yellow
            [255, 220, 150],   # orange
            [255, 170, 180],  # pink sunset
            [150, 220, 255], # night blue
        ]).transpose() / 255
        times=np.array((
            0, 4, 6, 8, 10, 12, 16, 18, 20, 22, 24))
        intensities=np.array((
            0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.0, 0.9, 0.75, 0.6, 0.5))
        angles=np.array((
            90, 45, 0, 25, 50, 75, 105, 130, 155, 180, 135))
        color = np.array((
            np.interp(self._daytime, times, np.array(colors[0])[0]),
            np.interp(self._daytime, times, np.array(colors[1])[0]),
            np.interp(self._daytime, times, np.array(colors[2])[0])
            ))
        I = np.interp(self._daytime, times, intensities)
        A = np.interp(self._daytime, times, angles)
        dif = I * 2/3
        amb = I * 1/3
        d = np.array((cos(A*pi/180),abs(sin(A*pi/180)), 0.9))

        self._light["ambient"] = color * amb
        self._light["diffuse"] = color * dif
        self._light["specular"] = 0.4
        self._light["shininess"] = 16
        self._light["dir"] = - d / np.linalg.norm(d)


    def imagesReady(self):
        return self._snake_images != None

    def getSnakeImages(self):
        return self._snake_images

    def loadAsyncMaster(self):
        print("Loading images, please wait...")
        self.initialLoad()

        while True:            
            print("I am the master, mouhahaha! *whipping the slaves*")

            # the time has changed
            self.updateLight()

            # Give work to the slaves
            for c in range(len(self._player_colors)):
                self._task_queue.put(c)
            
            # Whip the slaves until they finish
            self._task_queue.join()

            # Publish what they produced
            self._snake_images = self._image_factory
            self._is_initialized = True

            # Take some rest until next task
            time.sleep(1.0)


    def loadAsyncSlave(self):
        while True:
            task_id = self._task_queue.get()
            t=time.time()
            self._image_factory[task_id] = self.generateAllImages(self._player_colors[task_id])
            print("I am a slave and I have worked for free on task", task_id, "for", time.time()-t, "sec")
            self._task_queue.task_done()

    def initialLoad(self):
        self._raw = {}

        # Load all the images with rotations
        for r in DayAndNight.rotate:
            for st in DayAndNight.shape_type:
                for dt in DayAndNight.data_type:
                    # load image file
                    img = self.loadImage(self._filename_format % (st, dt))
                    # rotate image
                    if img != None:
                        self._raw[st+dt+str(r)] = pygame.transform.rotate(img, r)
                    else:
                        self._raw[st+dt+str(r)] = None
                
                w,h = self._raw[st+'diffuse'+str(r)].get_width(), self._raw[st+'diffuse'+str(r)].get_height()
                self._raw[st+'size'+str(r)] = (w,h)

                # convert normal map to matrix
                self._raw[st+'normal'+str(r)] = self.rotateNormalMap(self._raw[st+'normal'+str(r)], r, (w,h))

                # convert image mask to matrix
                self._raw[st+'specular'+str(r)] = self.createIntensityMatrixFromSurface(
                        self._raw[st+'specular'+str(r)])
                self._raw[st+'emissive'+str(r)] = self.createIntensityMatrixFromSurface(
                        self._raw[st+'emissive'+str(r)])

                # merge diffuse and hue map, per player
                for c in self._player_colors:
                    self._raw[st+'diffuse'+str(r)+str(c)], self._raw[st+'alpha'+str(r)] = self.mergeDiffuseAndHue(
                            self._raw[st+'diffuse'+str(r)],
                            self._raw[st+'team'+str(r)],
                            c)

    def rotateNormalMap(self, normal_map, rotate, size):
        if normal_map is None:
            return np.zeros((size[0], size[1], 3))
        
        w, h = normal_map.get_width(), normal_map.get_height()
        c, s = cos(radians(rotate)), sin(radians(rotate))
        matrix = np.matrix([[c,-s, 0],
                            [s, c, 0],
                            [0, 0, 1]])
        
        # surface to 3d matrix
        pxl = pygame.surfarray.array3d(normal_map).reshape((w*h, 3))
        # colors to vectors
        n = pxl / 127.5 - 1
        # apply rotation to vectors
        transformed = np.array(n * matrix)
        # normalize vectors
        transformed /= np.sqrt(np.einsum('...i,...i', transformed, transformed))[..., np.newaxis]
        new_map = transformed#.reshape((w,h,3))
        
        return new_map

    def mergeDiffuseAndHue(self, diffuse_map, new_color_mask, new_color):
        w, h = diffuse_map.get_width(), diffuse_map.get_height()
        
        # surface to 3d matrix, to range [0,1]
        diffuse = pygame.surfarray.array3d(diffuse_map) / 255
        # extract alpha channel from surface
        alpha_map = pygame.surfarray.array_alpha(diffuse_map)
        # mask surface to 2d matrix in range [0,1]
        mask = pygame.surfarray.array3d(new_color_mask).max(2) / 255 if new_color_mask != None else None
        
        # New color in HSV
        newH, newS, newV = colorsys.rgb_to_hsv(*(np.array(new_color)/255))
        
        colors = np.zeros(shape=(w,h,3), dtype=float)

        for x in range(w):
            for y in range(h):
                if alpha_map[x][y]:
                    color = diffuse[x][y]
            
                    if new_color_mask != None:
                        m = mask[x][y]
                        if m:
                            oldH, oldS, oldV = colorsys.rgb_to_hsv(*color)
                            if oldS*newS == 0:
                                H = oldH
                            else:
                                dH = newH-oldH
                                if dH < -0.5: dH += 1
                                elif dH > 0.5: dH -= 1
                                H = np.interp(m, [0,1], [oldH, oldH+dH])
                                if H < 0: H += 1
                                elif H >= 1: H -= 1
                            S = np.interp(m, [0,1], [1, newS]) * oldS
                            V = np.interp(m, [0,1], [1, newV]) * oldV
                            color = np.array(colorsys.hsv_to_rgb(H, S, V))
                    colors[x][y] = color

        return colors.reshape((w*h, 3)), alpha_map
    
    def createIntensityMatrixFromSurface(self, img):
        if img is None:
            return None

        w, h = img.get_width(), img.get_height()
        # surface to 3d matrix, min of each channel per pixel, to range [0,1]
        out = pygame.surfarray.array3d(img).reshape((w*h,3)).min(1) / 255

        return out
    
    def generateAllImages(self, player_color):
        images = {}
        
        for r in range(len(DayAndNight.rotate)):
            rotation = DayAndNight.rotate[r]
            images[((r+0)%6,(r+0)%6)] = self.makeImage('straight', rotation, player_color)
            images[((r+5)%6,(r+0)%6)] = self.makeImage('corner', rotation, player_color)
            images[((r+3)%6,(r+2)%6)] = images[((r+5)%6,(r+0)%6)]
            images[((r+0)%6,-1)] = self.makeImage('head', rotation, player_color)
            images[(-1,(r+3)%6)] = self.makeImage('tail', rotation, player_color)

        return images

    def makeImage(self, st, rotate, new_color):
        normal = self._raw[st+'normal'+str(rotate)]
        diffuse = self._raw[st+'diffuse'+str(rotate)+str(new_color)]
        alpha = self._raw[st+'alpha'+str(rotate)]
        emissive = self._raw[st+'emissive'+str(rotate)]
        specular = self._raw[st+'specular'+str(rotate)]
        w, h = self._raw[st+'size'+str(rotate)]

        l_dir = self._light["dir"]
        l_spe = self._light["specular"]
        l_dif = self._light["diffuse"]
        l_amb = self._light["ambient"]
        l_shi = self._light["shininess"]
        
        H = np.array((0,0,1)) - l_dir
        H /= np.linalg.norm(H)

        if specular is None:
            specular = l_spe
        if emissive is None:
            emissive = 0

        # compute lighting
        n_dot_dir = np.maximum(normal.dot(-l_dir), 0)
        spec = (np.maximum(normal.dot(H), 0) ** l_shi) * specular * np.bool_(n_dot_dir)
        diff = n_dot_dir[...,np.newaxis] * l_dif
        c = (diff + l_amb + emissive) * diffuse + spec[...,np.newaxis] * l_dif
        pixels = np.int_(np.clip(c * 255, 0, 255)).reshape((w,h,3))

        # convert to surface
        image_out = pygame.surfarray.make_surface(pixels).convert_alpha()

        # apply alpha mask
        out_alpha = pygame.surfarray.pixels_alpha(image_out)
        np.copyto(out_alpha, alpha)
        
        return image_out


    def loadImage(self, filename):
        try:
            return pygame.image.load(filename).convert_alpha()
        except:
            return None
