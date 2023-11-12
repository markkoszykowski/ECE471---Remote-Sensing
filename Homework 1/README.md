# Homework 1

## Task 1

In order to create a spatially aligned dataset, first the GeoJSON file was read, and a vector perimeter was extracted.
This perimeter was then sent to a function that cropped each GeoTIFF to fit within the given perimeter.
Then, a function was applied that iterated over the dataset, found the max absolute resolution (most granular resolution), and applied it to all the images in the dataset.
Resolution distributions were made, which indicated that ~10% of the data existed around this most granular resolution, which is why it was used.
The intent was to avoid as much data inferencing as possible.
A bilinear interpolation scheme was used so that surrounding "thrown-away" data was still incorporated.

## Task 2

### Histograms

![](front/histogram.png)

### Cloud Masking Algorithm

The first implementation of the cloud mask followed the Sentintel 2 Level 2A Algorithm (Referenced Below).
This algorithm executed based on the Level 1C data which was inferred to be provided based on the names of the files in the dataset and the band information.
The hope with this algorithm was that not only Dense clouds, but also Cirrus clouds would be identified effectively.
This implementation however, was not only quite computationally complex, but also did not do a very effective job of detecting generally cloudy pixels.

The next attempt used information from the Sentinel 2 Level 1C cloud mask guide (Referenced Below).
The guide made it clear that clouds, unlike snow, were not only relatively reflective in the blue (B2) band but also the SWIR1 (B11) and SWIR2 (B12) bands.
With this information, two simple ratios were created that were meant to emulate the common Normalized Difference Indexes in mathematical form.
The first ratio incorporated the blue (B2) and SWIR1 (B11) bands, and the second ratio incorporated the blue (B2) and SWIR2 (B12) bands.
Theoretically, clouds would have significantly higher values for these ratios than snow, making them easy to detect.
In order to be safe, the NDSI values of each pixel were also calculated and taken into account to minimize false detections.
In order to determine a threshold for these values, a plethora of individual pixels from different images and different land settings were manually tested.

The final product generally did quite an effective job of detecting clouds.
Using the provided 'seeCloudMask.py' script, cloud masks of each image were merged with the alpha mask so that they could be viewed in QGIS.
The downside of the created algorithm is that it occasionally identified clearly urban areas that were very reflective as clouds.
In order to combat this, an NDBI ratio was also calculated and thresholded.
This however, did not go well seeing as there were no clear distinctions between clouds and reflective urban areas in this value.
The upside was that not only did the algorithm effectively mask dense, cloudy pixels, it also masked cloud shadows quite well.

#### Very Cloudy Scene

|No Mask |  Mask|
|--------|------|
|![](front/6-3.PNG)  |  ![](front/6-3%20Masked.PNG)|

#### Minimal Cloudy Scene

|No Mask |  Mask|
|--------|------|
|![](front/5-4.PNG)  |  ![](front/5-4%20Masked.PNG)|

#### Snowy Scene

|No Mask |  Mask|
|--------|------|
|![](front/12-30.PNG)  |  ![](front/12-30%20Masked.PNG)|

#### Shadow Coverage

|No Mask |  Mask|
|--------|------|
|![](front/11-28.PNG)  |  ![](front/11-28%20Masked.PNG)|

### Finding the Greenest, Snowiest, Cloudiest, and Brightest Scenes

To determine the superlative scenes, mostly standard approaches were used.
For example, for the Greenest and Snowiest scenes, the Normalized Difference Indexes were used for each pixel, the average was taken across all the valid, non-cloud pixels, and the max was chosen as the respective superlative.
For the Cloudiest scene, a simple ratio of how many cloud masked pixels over the total amount of valid pixels was used.
For the Brightest scene, a Relative Luminance calculation was used (Referenced Below).

It turned out that the Snowiest scene was also the Brightest scene.
When determining (Greenest/Snowiest/Brightest) superlatives, ONLY valid and NON CLOUDY pixels were used, which creates a logical result.
Seeing as Santa Fe is not incredibly urban, it is brightest when it is snowiest since snow is very reflective in terms of the visual spectrum.

### Creating the Mean, Min, Max, Median, Greenest, and 85% Greenest Composite

Mostly standard computational methods were used.
In the Mean Composite, there is from artifacting where the left half of the image is slightly brighter than the right (there is a slightly visible line down the middle).
This is a result of multiple snowy scenes containing only valid data on the left, dragging down the mean values.
This type of artifacting is not as present on the Median Composite since medians are not as strongly effected by outliers.
Additionally, the Max image contains a large cloud that thresholding could not efficiently resolve.
This is because the visible cloud has a very high NDSI value, one that visibly snowy scenes did not quite match causing them to otherwise be identified as clouds.

### Output

    Creating Histograms...
    Adding Cloud Mask...
    Finding Greenest Scene...
    Greenest Scene: s2_santafe_spatially_aligned\sentinel-2_L1C_2018-09-04.tif
         Average NDVI: 0.23788154883969684
    Finding Snowiest Scene...
    Snowiest Scene: s2_santafe_spatially_aligned\sentinel-2_L1C_2018-12-30.tif
         Average NDSI: 0.7825624259627408
    Finding Cloudiest Scene...
    Cloudiest Scene: s2_santafe_spatially_aligned\sentinel-2_L1C_2018-11-10.tif
         Ratio of Cloud Masked Pixels: 0.8309104903140482
    Finding Brightest Scene...
    Brightest Scene: s2_santafe_spatially_aligned\sentinel-2_L1C_2018-12-30.tif
         Average Relative Luminance: 5766.51933394326
    Creating Mean Composite...
    Done, Output: composites\mean.tif
    Creating Min Composite...
    Done, Output: composites\min.tif
    Creating Max Composite...
    Done, Output: composites\max.tif
    Creating Median Composite...
    Done, Output: composites\median.tif
    Creating Greenest Composite...
    Done, Output: composites\greenest.tif
    Creating 85% Greenest Composite...
    Done, Output: composites\greenest85.tif

## References

 - [Ernesto Colon](https://github.com/ecolon08)
 - [Sentinel 2 Level 1C Cloud Masking](https://sentinel.esa.int/web/sentinel/technical-guides/sentinel-2-msi/level-1c/cloud-masks)
 - [Sentinel 2 Level 2A Cloud Masking](https://sentinel.esa.int/web/sentinel/technical-guides/sentinel-2-msi/level-2a/algorithm)
 - [Relative Luminance](https://stackoverflow.com/questions/596216/formula-to-determine-brightness-of-rgb-color)