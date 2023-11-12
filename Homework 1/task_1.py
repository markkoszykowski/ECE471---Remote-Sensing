import os
import sys
import json
import shutil
from osgeo import gdal

## Mark Koszykowski
## ECE472 - Remote Sensing
## Homework 1 - Problem 1 Task 1

# Defining relative PATHs
temp_dir = "tmp"
GeoTIF_dir = "s2_santafe"
align_dir = GeoTIF_dir + "_spatially_aligned"
GeoJSON = "santafe_crop.geojson"


# Function to extract min/max square dimensions from JSON
def getOutputBounds(path):
    with open(path) as jsonFile:
        data = json.load(jsonFile)
        vector = data['features'][0]['geometry']

    lat = []
    long = []

    for e in vector['coordinates'][0]:
        long.append(e[0])
        lat.append(e[1])

    # Return the min/max box coordinates
    return min(long), min(lat), max(long), max(lat)


# Function to crop dataset to certain bounds (projecting to EPSG:4326)
def cropData(srcPath, destPath, outputBounds):
    print("Cropping dataset...")
    for GeoTIF in os.listdir(srcPath):
        gdal.Warp(destPath + '\\' + GeoTIF, srcPath + '\\' + GeoTIF,
                  outputBounds=outputBounds, dstSRS='EPSG:4326')


# Function to ensure whole dataset has same resolution
def normData(srcPath, destPath):
    print("Resampling dataset...")
    xResList = []
    yResList = []

    # Retrieve resolutions of each image
    for GeoTIF in os.listdir(srcPath):
        dataset = gdal.Open(srcPath + '\\' + GeoTIF)
        _, xRes, _, _, _, yRes = dataset.GetGeoTransform()
        xResList.append(xRes)
        yResList.append(yRes)

    # xRes are positive
    # yRes are negative
    for GeoTIF in os.listdir(srcPath):
        gdal.Warp(destPath + '\\' + GeoTIF, srcPath + '\\' + GeoTIF,
                  xRes=max(xResList), yRes=min(yResList), resampleAlg=gdal.GRA_Bilinear)


# Main execution to complete task 1
if __name__ == "__main__":
    print("Creating Spatially Aligned data...")

    # Create necessary directories
    try:
        os.mkdir(align_dir)
        os.mkdir(temp_dir)
    except:
        sys.exit("Spatially Aligned data already exists")

    outputBounds = getOutputBounds(GeoJSON)
    cropData(GeoTIF_dir, temp_dir, outputBounds)
    normData(temp_dir, align_dir)

    # Remove /tmp directory
    try:
        shutil.rmtree(temp_dir)
    except:
        sys.exit("Failed to delete /tmp directory")

    print("Done.")