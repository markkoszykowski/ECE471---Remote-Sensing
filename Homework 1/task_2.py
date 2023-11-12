import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from osgeo import gdal

## Mark Koszykowski
## ECE472 - Remote Sensing
## Homework 1 - Problem 1 Task 2

# Defining relative PATHs
GeoTIF_dir = "s2_santafe_spatially_aligned"
composites_dir = "composites"


# Function that loads Spatially Aligned data into a list of numpy arrays for manipulation
def loadImages(path):
    images = []
    labels = []
    geoTransform = None
    projection = None
    for GeoTIF in os.listdir(path):
        labels.append(path + '\\' + GeoTIF)
        dataset = gdal.Open(path + '\\' + GeoTIF)
        geoTransform = dataset.GetGeoTransform()
        projection = dataset.GetProjection()
        img = dataset.ReadAsArray()
        images.append(img)

    return images, labels, geoTransform, projection


# Function to plot histograms of data over time
def createHistogram(data):
    print("Creating Histograms...")
    bands, height, width = data[0].shape
    bands -= 1
    bandNames = ["Red", "Green", "Blue", "NIR", "SWIR1", "SWIR2"]
    bandColors = ["red", "green", "blue", "magenta", "aqua", "darkviolet"]
    fig, axs = plt.subplots(2, 3)
    axs = axs.ravel()
    for c in range(bands):
        values = []
        for image in data:
            for j in range(height):
                for k in range(width):
                    if image[6, j, k] > 0:
                        values.append(image[c, j, k])
        axs[c].hist(x=values, bins=10000, color=bandColors[c])
        axs[c].set_title(bandNames[c] + " Band")
        axs[c].set_xlabel("Intensity")
        axs[c].set_ylabel("Count")
    plt.show()


# Function to create simple cloud mask
#   Similar scheme to alpha band
#   0 -> Cloud Pixel
#   65535 -> Valid Pixel
#  [red, green, blue, nir, swir1, swir2, alpha, cloud mask]
def createCloudMask(data):
    print("Adding Cloud Mask...")
    output = []
    for image in data:
        bands, height, width = image.shape
        # By default, set all pixels to cloudless
        newImage = np.full((bands + 1, height, width), 65535)
        newImage[:bands, :, :] = image
        for j in range(height):
            for k in range(width):
                # Only check for clouds within alpha-valid pixels (necessary for calculating cloudiest image)
                if newImage[6, j, k] > 0:
                    NDSI = (newImage[1, j, k] - newImage[4, j, k]) / (newImage[1, j, k] + newImage[4, j, k])
                    ratio1 = (newImage[2, j, k] - newImage[4, j, k]) / (newImage[2, j, k] + newImage[4, j, k])
                    ratio2 = (newImage[2, j, k] - newImage[5, j, k]) / (newImage[2, j, k] + newImage[5, j, k])
                    # Check thresholds
                    if -.13 <= ratio1 and -.13 <= ratio2 and NDSI <= .4:
                        newImage[7, j, k] = 0
        output.append(newImage)
    return output


# Function that uses standard NDVI to determine greenest scene (does not include alpha/cloud masked pixels)
# NDVI = (NIR - Red) / (NIR + Red)
def findGreenest(data, labels):
    print("Finding Greenest Scene...")
    _, height, width = data[0].shape
    NDVI = []

    for image in data:
        # Create a mask that invalidates cloudy/zero-alpha pixels
        fullMask = np.logical_and((image[6, :, :] > 0), (image[7, :, :] > 0))
        NDVIraster = np.zeros((height, width))
        for j in range(height):
            for k in range(width):
                if fullMask[j, k]:
                    NDVIraster[j, k] = (image[3, j, k] - image[0, j, k]) / (image[3, j, k] + image[0, j, k])
        NDVIavg = np.sum(NDVIraster) / np.count_nonzero(fullMask == True)

        NDVI.append(NDVIavg)

    print(F"Greenest Scene: {labels[np.argmax(NDVI)]}")
    print(F"     Average NDVI: {max(NDVI)}")


# Function that uses standard NDSI to determine snowiest scene (does not include alpha/cloud masked pixels)
# NDSI = (Green - SWIR1) / (Green + SWIR1)
def findSnowiest(data, labels):
    print("Finding Snowiest Scene...")
    _, height, width = data[0].shape
    NDSI = []

    for image in data:
        # Create a mask that invalidates cloudy/zero-alpha pixels
        fullMask = np.logical_and((image[6, :, :] > 0), (image[7, :, :] > 0))
        NDSIraster = np.zeros((height, width))
        for j in range(height):
            for k in range(width):
                if fullMask[j, k]:
                    NDSIraster[j, k] = (image[1, j, k] - image[4, j, k]) / (image[1, j, k] + image[4, j, k])
        NDSIavg = np.sum(NDSIraster) / np.count_nonzero(fullMask == True)

        NDSI.append(NDSIavg)

    print(F"Snowiest Scene: {labels[np.argmax(NDSI)]}")
    print(F"     Average NDSI: {max(NDSI)}")


# Function that counts cloud masked pixels to determine cloudiest scene
# "NDCI" = Number of pixels with clouds / Number of valid pixels
def findCloudiest(data, labels):
    print("Finding Cloudiest Scene...")
    NDCI = []

    for image in data:
        NDCI.append(np.count_nonzero(image[7, :, :] == 0) / np.count_nonzero(image[6, :, :] == 65535))

    print(F"Cloudiest Scene: {labels[np.argmax(NDCI)]}")
    print(F"     Ratio of Cloud Masked Pixels: {max(NDCI)}")


# Function that uses relative luminance to determine brightest scene (does not include alpha/cloud masked pixels)
# "NDBI" (Relative Luminance) = .2126 * Red + .7152 * Green + .0722 * Blue
# Source for calculation: https://stackoverflow.com/questions/596216/formula-to-determine-brightness-of-rgb-color
def findBrightest(data, labels):
    print("Finding Brightest Scene...")
    _, height, width = data[0].shape
    NDBI = []

    for image in data:
        # Create a mask that invalidates cloudy/zero-alpha pixels
        fullMask = np.logical_and((image[6, :, :] > 0), (image[7, :, :] > 0))
        NDBIraster = np.zeros((height, width))
        for j in range(height):
            for k in range(width):
                if fullMask[j, k]:
                    NDBIraster[j, k] = .2126 * image[0, j, k] + .7152 * image[1, j, k] + .0722 * image[2, j, k]
        NDBIavg = np.sum(NDBIraster) / np.count_nonzero(fullMask == True)

        NDBI.append(NDBIavg)

    print(F"Brightest Scene: {labels[np.argmax(NDBI)]}")
    print(F"     Average Relative Luminance: {max(NDBI)}")


# Function to create Mean composite
def makeMean(data, path, geoTransform, projection):
    print("Creating Mean Composite...")
    bands, height, width = data[0].shape
    mean = np.zeros((bands, height, width))
    tot = np.zeros((bands, height, width))

    # Simply adds values of valid pixels to a numpy array while keeping track of how many valid values for each pixel
    for image in data:
        for j in range(height):
            for k in range(width):
                if image[6, j, k] > 0 and image[7, j, k] > 0:
                    mean[:, j, k] += image[:, j, k]
                    tot[:, j, k] += 1

    mean = mean / tot
    createTif(path + '\\' + "mean.tif", mean,
              width, height, bands, geoTransform, projection)


# Function to create Min composite
def makeMin(data, path, geoTransform, projection):
    print("Creating Min Composite...")
    bands, height, width = data[0].shape
    minIm = np.full((bands, height, width), 16384)

    # Iterates through each band of each pixel of each image to find the minimum value for each band in a pixel
    for image in data:
        for j in range(height):
            for k in range(width):
                if image[6, j, k] > 0 and image[7, j, k] > 0:
                    for c in range(bands):
                        minIm[c, j, k] = min(minIm[c, j, k], image[c, j, k])

    createTif(path + '\\' + "min.tif", minIm,
              width, height, bands, geoTransform, projection)


# Function to create Max composite
def makeMax(data, path, geoTransform, projection):
    print("Creating Max Composite...")
    bands, height, width = data[0].shape
    maxIm = np.zeros((bands, height, width))

    # Iterates through each band of each pixel of each image to find the maximum value for each band in a pixel
    for image in data:
        for j in range(height):
            for k in range(width):
                if image[6, j, k] > 0 and image[7, j, k] > 0:
                    for c in range(bands):
                        maxIm[c, j, k] = max(maxIm[c, j, k], image[c, j, k])

    createTif(path + '\\' + "max.tif", maxIm,
              width, height, bands, geoTransform, projection)


# Function to create Median composite
def makeMedian(data, path, geoTransform, projection):
    print("Creating Median Composite...")
    bands, height, width = data[0].shape
    median = np.zeros((bands, height, width))

    # Appends valid values of each band of each pixel to a list of lists, and sets the result equal to the median
    for j in range(height):
        for k in range(width):
            LoL = [[] for c in range(bands)]
            for image in data:
                if image[6, j, k] > 0 and image[7, j, k] > 0:
                    for c in range(bands):
                        LoL[c].append(image[c, j, k])
            for c in range(bands):
                median[c, j, k] = np.median(LoL[c])

    createTif(path + '\\' + "median.tif", median,
              width, height, bands, geoTransform, projection)


# Function to create Greenest composite
def makeGreenest(data, path, geoTransform, projection):
    print("Creating Greenest Composite...")
    bands, height, width = data[0].shape
    greenest = np.zeros((bands, height, width))

    # Appends NDVI values of each pixel to an array, finds the index of the max, and sets result equal to that image's
    # pixel value "packet" (package of 7 bands)
    for j in range(height):
        for k in range(width):
            NDVI = np.zeros((len(data),))
            i = 0
            for image in data:
                if image[6, j, k] > 0 and image[7, j, k] > 0:
                    NDVI[i] = (image[3, j, k] - image[0, j, k]) / (image[3, j, k] + image[0, j, k])
                # If pixel is invalid/cloudy, set NDVI below minimum value
                else:
                    NDVI[i] = -2
                i += 1
            greenest[:, j, k] = data[np.argmax(NDVI)][:, j, k]

    bands, height, width = greenest.shape
    createTif(path + '\\' + "greenest.tif", greenest,
              width, height, bands, geoTransform, projection)


# Function to create 85% Greenest composite
def make85Greenest(data, path, geoTransform, projection):
    print("Creating 85% Greenest Composite...")
    bands, height, width = data[0].shape
    greenest85 = np.zeros((bands, height, width))

    # Appends NDVI values of each pixel to an array, removes invalid values in the array, sorts the array, gets the
    # index of the 85th percentile, and sets result equal to that image's pixel value "packet" (package of 7 bands)
    for j in range(height):
        for k in range(width):
            NDVI = np.zeros((len(data),))
            i = 0
            for image in data:
                if image[6, j, k] > 0 and image[7, j, k] > 0:
                    NDVI[i] = (image[3, j, k] - image[0, j, k]) / (image[3, j, k] + image[0, j, k])
                # If pixel is invalid/cloudy, set NDVI below minimum value
                else:
                    NDVI[i] = -2
                i += 1
            sortedNDVI = np.sort(np.delete(NDVI, np.where(NDVI == -2)))

            greenest85[:, j, k] = data[np.where(NDVI == sortedNDVI[round(.85 * len(sortedNDVI)) - 1])[0][0]][:, j, k]

    bands, height, width = greenest85.shape
    createTif(path + '\\' + "greenest85.tif", greenest85,
              width, height, bands, geoTransform, projection)


# Abstract function to create a GeoTIFF composite from numpy array
def createTif(name, data, width, height, bands, geoTransform, projection):
    bands -= 1  # Exclude cloud mask
    driver = gdal.GetDriverByName('GTiff')
    tif = driver.Create(name, width, height, bands, gdal.GDT_UInt16)
    tif.SetGeoTransform(geoTransform)
    tif.SetProjection(projection)
    for band in range(bands):
        tif.GetRasterBand(band + 1).WriteArray(data[band, :, :])
    tif.FlushCache()
    tif = None
    print("Done, Output: " + name)


# Main execution to complete task 2
if __name__ == "__main__":
    images, labels, geoTransform, projection = loadImages(GeoTIF_dir)
    createHistogram(images)
    images = createCloudMask(images)

    findGreenest(images, labels)
    findSnowiest(images, labels)
    findCloudiest(images, labels)
    findBrightest(images, labels)

    # Create necessary directory
    try:
        os.mkdir(composites_dir)
    except:
        sys.exit("Task 2 Composites already exist")

    makeMean(images, composites_dir, geoTransform, projection)
    makeMin(images, composites_dir, geoTransform, projection)
    makeMax(images, composites_dir, geoTransform, projection)
    makeMedian(images, composites_dir, geoTransform, projection)
    makeGreenest(images, composites_dir, geoTransform, projection)
    make85Greenest(images, composites_dir, geoTransform, projection)
