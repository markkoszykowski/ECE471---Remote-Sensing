# -*- coding: utf-8 -*-
"""ECE471_Final_Project.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1ccM0rw-k4GQNkoDuZUoVV-Yu7WJDG2y7

# Final Project
# Analysis of Coastal Erosion along Puerto Rican Borderline
## Mark Koszykowski, Steven Lee, Allister Liu

# Produce Data
"""

# Import data from GEE and declare start and end dates

# Sentinel 2 Data
sentIc = ee.ImageCollection("COPERNICUS/S2_SR")
# ERA5 Daily Data
tempIc = ee.ImageCollection("ECMWF/ERA5/DAILY")

start_date = '2017-03-28'
end_date = '2020-07-08'

# Function to create a single layer bit mask for relevant classes
# Used later to create targets for model
def get_class_mask(image):
  scl_layer = image.select('SCL')
  water_mask = scl_layer.eq(6).multiply(2)
  # attribute saturated/defective, medium cloud probability, high cloud probability, and cirrus pixels to 0
  # attribute water pixels to 2
  # and everything thats not in the above categories is assumed to be land pixel (to 1)
  cloud_mask = scl_layer.eq(1).Or(scl_layer.eq(8)).Or(scl_layer.eq(9)).Or(scl_layer.eq(10)).Not()
  final_mask = cloud_mask.max(water_mask)
  return final_mask

# Function to combine all input data into one image collection

desired_sent_bands = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']
desired_era5_bands = ['mean_2m_air_temperature',
                      'minimum_2m_air_temperature',
                      'maximum_2m_air_temperature',
                      'dewpoint_2m_temperature',
                      'total_precipitation',
                      'surface_pressure',
                      'mean_sea_level_pressure',
                      'u_component_of_wind_10m',
                      'v_component_of_wind_10m']

def combine_collections(image):
  reduced_bands = image.select(desired_sent_bands)
  water_mask = image.select('SCL').eq(6)
  date = image.date()
  era_image = tempIc.filterDate(date, date.advance(23, 'hour')).first()
  full_bands = reduced_bands.addBands(era_image, desired_era5_bands)
  return full_bands

# Function to create the targets based on the class masks made previously
def make_target(image, list):
  list = ee.List(list)
  previous = ee.Image(list.get(-1))
  image = ee.Image(image)
  trg = previous.eq(1).And(image.eq(2))
  return list.add(trg)

# Function to loop over the GeoJSONs made and import GEE data based on region
def produce_data_from_geojson(geojson):
  name = os.path.basename(geojson).split('.')[0]
  print(geojson)
  with open(geojson, 'r') as f:
    fc = json.load(f)

  # Extract geometry
  geometry = fc['features'][0]['geometry']['coordinates'][0]

  area = ee.Geometry.Polygon(geometry)

  # Filter dates
  areaTempIc = tempIc.filterBounds(area).filterDate(start_date, end_date)

  start_year = int(start_date.split('-')[0])
  start_month = int(start_date.split('-')[1])
  end_year = int(end_date.split('-')[0])
  end_month = int(end_date.split('-')[1])

  # Only retrieve one image per month max
  areaSentImages = []
  for year in range(start_year, end_year+1):
    for month in range(1, 13):
      if year == start_year and month < start_month:
        continue
      elif year == end_year and month > end_month:
        continue
      else:
        areaSentImages.append(ee.Image(sentIc.filterBounds(area).filterDate(F"{year}-{month}-1", F"{year}-{month}-28").filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).first()))

  areaSentIc = ee.ImageCollection(areaSentImages)

  # Print out dates to ensure somewhat normal
  dates = ee.List(areaSentIc.aggregate_array('system:time_start')).map(lambda time: ee.Date(time).format()).getInfo()
  print(F"Dates ({len(dates)}):")
  print(dates)

  areaClassIc = areaSentIc.map(get_class_mask)
  print(F"Size of class IC: {areaClassIc.size().getInfo()}")

  areaFullIc = areaSentIc.map(combine_collections)
  print(F"Size of combined IC: {areaClassIc.size().getInfo()}")

  areaList = areaClassIc.toList(areaClassIc.size())
  
  init = areaList.slice(0, 1)
  rest = areaList.slice(1)

  # produce the targets from the class image stack
  areaTargetList = ee.List(rest.iterate(make_target, init))
  areaTargetIc = ee.ImageCollection.fromImages(areaTargetList.slice(1))
  # Size of this list should be one less than previous two since it is the difference
  print(F"Size of target IC: {areaTargetIc.size().getInfo()}")

  return areaClassIc, areaFullIc, areaTargetIc, area, name

# Function to download images to Drive from Image Collection
def produce_csv_and_download(list_of_ICtuples):
  list_of_train_df = []
  list_of_test_df = []

  # GEE can only export to private drive so must mount that
  drive.mount('/content/gdrive')
  for i, tuple_of_IC in enumerate(list_of_ICtuples):
    imageIc = tuple_of_IC[0]
    targetIc = tuple_of_IC[1]
    area = tuple_of_IC[2]
    name = tuple_of_IC[3]

    tot_size = imageIc.size().getInfo()
    train_size = targetIc.size().getInfo()

    imageList = imageIc.toList(tot_size)
    targetList = targetIc.toList(train_size)

    # Save to /images directory
    for j in range(tot_size):
      image = ee.Image(imageList.get(j)).toFloat()
      image_name = name + image.getInfo()['properties']['system:index']
      task = ee.batch.Export.image.toDrive(image=image, description=image_name, region=area, folder="ECE471_images", dimensions="256x256")
      if j == train_size:
        list_of_test_df.append("/images/" + image_name)
      else:
        target = ee.Image(targetList.get(j))
        list_of_train_df.append(["/images/" + image_name, "/images/" + name + target.getInfo()['properties']['system:index']])
      task.start()
      print(task.status())

    for j in range(train_size):
      target = ee.Image(targetList.get(j))
      target_name = name + target.getInfo()['properties']['system:index']
      task = ee.batch.Export.image.toDrive(image=target, description=target_name, region=area, folder="ECE471_images", dimensions="256x256")
      task.start()
      print(task.status())

  train_csv = pd.DataFrame(list_of_train_df, columns=['images', 'targets'])
  test_csv = pd.DataFrame(list_of_test_df, columns=['images'])

  drive.mount('/content/ECE471')
  # Put respective file names in property CSVs
  train_csv.to_csv(r'/content/ECE471/Shareddrives/ECE471/train.csv', index=False, header=True)
  test_csv.to_csv(r'/content/ECE471/Shareddrives/ECE471/test.csv', index=False, header=True)

files = glob.glob('/content/ECE471/Shareddrives/ECE471/GeoJSON_named/*.geojson')
print(files)
print()

list_of_ICs = []

# Call premade functions for each GeoJSON
for i, file in enumerate(files):
  classIc, fullIc, targetIc, area, name = produce_data_from_geojson(file)
  list_of_ICs.append((fullIc, targetIc, area, name))
  # save a batch of ICs locally to display
  if i == 63:
    class_example = classIc
    full_example = fullIc
    target_example = targetIc
    area_example = area

# Extract the centroid for visualizaation
center = area_example.centroid().getInfo()['coordinates']
center.reverse()
print(center)

# Visualize the combined train data
img = full_example.first()

Map = geemap.Map(center=ce
nter, zoom=14)

visualization = {
  'min': 0.0,
  'max': 3000,
  'bands': ['B4', 'B3', 'B2'],
}

Map.add_layer(img, visualization, 'first sentinel image')
Map.add_layer(ee.FeatureCollection(area_example), {}, "outline")
Map

# Visualize the combined train data
img = full_example.first().select('mean_2m_air_temperature')

Map = geemap.Map(center=center, zoom=14)

visualization = {
  'min': 290,
  'max': 305,
  'palette': ['cyan', 'red'],
}

Map.add_layer(img, visualization, 'first era5 image')
Map.add_layer(ee.FeatureCollection(area_example), {}, "outline")
Map

# Visualize the class data
img = class_example.first()

Map = geemap.Map(center=center, zoom=14)

visualization = {
  'min': 0.0,
  'max': 2.0,
  'palette': ['white', 'brown', 'blue'],
}

Map.add_layer(img, visualization, 'first temperature image of full dataset')
Map.add_layer(ee.FeatureCollection(area_example), {}, "outline")
Map

# Visualize the target data on top of the image data
img = full_example.first()

Map = geemap.Map(center=center, zoom=14)

visualization1 = {
  'min': 0.0,
  'max': 3000,
  'bands': ['B4', 'B3', 'B2'],
}

tgt = target_example.first()

visualization2 = {
  'min': 0.0,
  'max': 1,
  'palette': ['white', 'red'],
}

Map.add_layer(img, visualization1, "first color image of full dataset")
Map.add_layer(tgt, visualization2, 'first target image')
Map.add_layer(ee.FeatureCollection(area_example), {}, "outline")
Map

# Downloads images to private drive and then puts data in CSVs
produce_csv_and_download(list_of_ICs)

"""## MUST WAIT UNTIL ALL IMAGES EXPORT TO RUN THIS CELL"""

# Moving data from personal Drive to Shared Drive

drive.mount('/content/gdrive')

# Must create simulink in personal Drive before running this command
# Right click on /images folder and press "Add Shortcut to Drive"

!cp -r '/content/gdrive/MyDrive/ECE471_images/.' '/content/gdrive/MyDrive/images'

drive.mount('/content/ECE471')
!ls /content/ECE471/Shareddrives/ECE471/images

"""# Preparation ("Run After" from here)"""

# Mount Google Drive for Externally obtained data

from google.colab import drive
drive.mount('/content/ECE471')
!ls /content/ECE471/Shareddrives/ECE471/
!mkdir -p /content/ECE471/Shareddrives/ECE471/images

# Install geemap
# Must run once and then restart runtime and run again to get no errors

!pip install geemap
!pip install geetools
!pip install rasterio
!pip install tensorflow-addons

"""# Imports"""

# Imports and GEE authentication/initialization

import os
import ee
ee.Authenticate()
ee.Initialize()
import geemap
import geetools
import rasterio
import rasterio.warp
import folium
import glob
import json
import pandas as pd
import numpy as np
import tensorflow as tf
import tensorflow_addons as tfa
import matplotlib.pyplot as plt
from tqdm.notebook import tqdm
from scipy import signal
from random import shuffle
from shapely.geometry import box, mapping

"""# Import Data into TF Dataset"""

# Import the data CSVs
train_df = pd.read_csv('/content/ECE471/Shareddrives/ECE471/train.csv')
test_df = pd.read_csv('/content/ECE471/Shareddrives/ECE471/test.csv')
print(len(train_df))
print(len(test_df))

train_df.head(5)

test_df.head(5)

# Produce the lists of data in similar formate to Homework 2
train_samples = []
test_samples = []
for ind, row in train_df.iterrows():
  image_file = 'ECE471/Shareddrives/ECE471' + row['images'] + '.tif'
  target_file = 'ECE471/Shareddrives/ECE471' + row['targets'] + '.tif'

  train_samples.append((image_file, target_file))

for ind, row in test_df.iterrows():
  test_samples.append('ECE471/Shareddrives/ECE471' + row['images'] + '.tif')

# Get idea of the format of the images
with rasterio.open(train_samples[0][0]) as src:
  img = src.read()

with rasterio.open(train_samples[0][1]) as src:
  tgt = src.read()

with rasterio.open(test_samples[0]) as src:
  test_img = src.read()

print(img.shape)
print(tgt.shape)
print(test_img.shape)

print(len(train_samples))
print(len(test_samples))

# Function to import image as numpy array
def train_read_sample(data_path: str) -> tuple:
  path = data_path.numpy()
  image_path, target_path = path[0].decode('utf-8'), path[1].decode('utf-8')

  with rasterio.open(image_path) as src:
    img = np.transpose(src.read(), axes=(1, 2, 0)).astype(np.float32)

  with rasterio.open(target_path) as src:
    tgt = np.transpose(src.read(), axes=(1, 2, 0)).astype(np.float32)

  return (img, tgt)

# Function to import numpy arrays and return dictionary
@tf.function
def tf_train_read_sample(data_path: str) -> dict:
  [image, target] = tf.py_function(train_read_sample, [data_path], [tf.float32, tf.float32])

  image.set_shape((256, 256, 20))
  target.set_shape((256, 256, 1))

  return {'image': image, 'target': target}

# Function to import dictionary and turn into Tensors
@tf.function
def train_load_sample(sample: dict) -> tuple:
  image = tf.image.resize(sample['image'], (256, 256))
  target = tf.image.resize(sample['target'], (256, 256))

  image = tf.cast(image, tf.float32)
  target = tf.cast(target, tf.float32)

  return image, target

# Apply functions to list and create tf.Dataset
train_ds = tf.data.Dataset.from_tensor_slices(train_samples)

train_ds = train_ds.map(tf_train_read_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

train_ds = train_ds.map(train_load_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

# Function to import test data as numpy array
def test_read_sample(data_path: str) -> np.array:
  image_path = data_path.numpy().decode('utf-8')

  with rasterio.open(image_path) as src:
    img = np.transpose(src.read(), axes=(1, 2, 0)).astype(np.float32)

  return img

# Function to import numpy array and return dictionary
@tf.function
def tf_test_read_sample(data_path: str) -> dict:
  image = tf.py_function(test_read_sample, [data_path], [tf.float32])

  image[0].set_shape((256, 256, 20))

  return {'image': image[0]}

# Function to import dictionary and turn test data into Tensors
@tf.function
def test_load_sample(sample: dict) -> tf.Tensor:
  image = tf.image.resize(sample['image'], (256, 256))

  image = tf.cast(image, tf.float32)

  return image

# Apply functions to test list and create tf.Dataset
test_ds = tf.data.Dataset.from_tensor_slices(test_samples)

test_ds = test_ds.map(tf_test_read_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

test_ds = test_ds.map(test_load_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

"""# Visualization"""

# Function to display coastal erosion mask on top of image
def display_image_target(display_list):
  plt.figure(dpi=400)
  title = ['Image', 'Coastal Erosion Highlighted']

  for idx, disp in enumerate(display_list):
    plt.subplot(1, len(display_list), idx+1)
    plt.title(title[idx], fontsize=6)
    plt.axis('off')

    if title[idx] == 'Image':
      arr = disp.numpy()
      rgb = np.stack([arr[:, :, 3], arr[:, :, 2], arr[:, :, 1]], axis=-1) / 3000.0
      plt.imshow(rgb)

    elif title[idx] == 'Coastal Erosion Highlighted':
      arr = display_list[0]
      filter = np.array([[1/16, 2/16, 1/16],
                         [2/16, 4/16, 2/16],
                         [1/16, 2/16, 1/16]])
      CA = 5000.0 * np.squeeze(disp.numpy())
      CA = signal.convolve2d(CA, filter, mode='same', boundary='fill')
      rgb = np.stack([arr[:, :, 3] + CA, arr[:, :, 2] - CA, arr[:, :, 1] - CA], axis=-1) / 3000.0
      plt.imshow(rgb)

  plt.show()
  plt.close()

# Display some of the training data
for image, target in train_ds.take(50):
  display_image_target([image, target])

# Display some of the test data
for image in test_ds.take(50):
  display_image_target([image])

# Extract coordinates from images as sanity check
coordinates = []
dst_crs = 'EPSG:4326'
for sample in tqdm(train_samples):
  with rasterio.open(sample[0]) as src:
    out_bounds = rasterio.warp.transform_bounds(src.crs,
                                                dst_crs,
                                                src.bounds.left,
                                                src.bounds.bottom,
                                                src.bounds.right,
                                                src.bounds.top)
  geom = box(*out_bounds)

  coordinate_pair = mapping(geom.centroid)
  coordinates.append(coordinate_pair)

# Look at format of return type
coordinates[0]

# Check the regions of interest
map = folium.Map(location=[18.45, -66.47], zoom_start=10)

for coordinate_pair in coordinates:
  folium.CircleMarker(location=[coordinate_pair['coordinates'][1], coordinate_pair['coordinates'][0]], radius=3, weight=3).add_to(map)

map

"""# Data Analysis"""

class_counts = {
    0: 0,
    1: 0
}
no_coastal_erosion = 0
num_NaN = 0
num_images_with_NaN = 0

# Calculate the number of pixels in each class as well as other factors used for data analysis
for image, target in tqdm(train_ds.take(len(train_samples)), total=len(train_samples)):
  tempNaN = np.count_nonzero(np.isnan(image.numpy()[:, :, 0]))
  if tempNaN > 0:
    num_images_with_NaN += 1
  num_NaN += tempNaN
  temp1 = np.count_nonzero(target.numpy() == 1)
  if temp1 == 0:
    no_coastal_erosion += 1
  class_counts[0] += np.count_nonzero(target.numpy() == 0)
  class_counts[1] += temp1

tot = sum(class_counts.values())
class_counts[0] /= tot
class_counts[1] /= tot

print(class_counts)
print(no_coastal_erosion)
print(num_NaN)
print(num_images_with_NaN)

# Visualize class distribution
bar_colors = ["green", "red"]

plt.figure(figsize=(20, 12))
plt.bar(["No Coastal Erosion", "Coast Erosion"], class_counts.values(), color=bar_colors)
for ind, count in enumerate(class_counts.values()):
  plt.annotate(str(count),
               xy=(ind, count),
               xytext=(0, 3),
               textcoords='offset points',
               ha='center', va='bottom')
plt.title("Total Pixel Distribution")
plt.show()

new_class_counts = {
    0: 0,
    1: 0
}
size = 0
new_num_NaN = 0
new_num_images_with_NaN = 0

# Save indices of images with no coastal erosion observed in the future while observing new dataset properties
ind_of_invalid = []

for ind, (image, target) in enumerate(tqdm(train_ds.take(len(train_samples)), total=len(train_samples))):
  temp1 = np.count_nonzero(target.numpy() == 1)
  if temp1 == 0:
    ind_of_invalid.append(ind)
    continue
  tempNaN = np.count_nonzero(np.isnan(image.numpy()[:, :, 0]))
  if tempNaN > 0:
    new_num_images_with_NaN += 1
  new_num_NaN += tempNaN
  new_class_counts[0] += np.count_nonzero(target.numpy() == 0)
  new_class_counts[1] += temp1
  size += 1

new_tot = sum(new_class_counts.values())
new_class_counts[0] /= new_tot
new_class_counts[1] /= new_tot

print(new_class_counts)
print(size)
print(new_num_NaN)
print(new_num_NaN / (256 * 256 * size))
print(new_num_images_with_NaN)

# Visualize new data distribution
bar_colors = ["green", "red"]

plt.figure(figsize=(20, 12))
plt.bar(["No Coastal Erosion", "Coast Erosion"], new_class_counts.values(), color=bar_colors)
for ind, count in enumerate(new_class_counts.values()):
  plt.annotate(str(count),
               xy=(ind, count),
               xytext=(0, 3),
               textcoords='offset points',
               ha='center', va='bottom')
plt.title("Valid Pixel Distribution")
plt.show()

num_NaN_test = 0
num_test_images_with_NaN = 0

# Get data properties on the test set to help determine factors about what should be left in training set
for image in tqdm(test_ds.take(len(test_samples)), total=len(test_samples)):
  temp = np.count_nonzero(np.isnan(image.numpy()[:, :, 0]))
  if temp > 0:
    num_test_images_with_NaN += 1
  num_NaN_test += temp

print(num_NaN_test)
print(num_NaN_test / (256 * 256 * len(test_samples)))
print(num_test_images_with_NaN)

# Create a new less inbalanced training set
new_train_samples = []
for ind, sample in enumerate(train_samples):
  if ind in ind_of_invalid:
    continue
  new_train_samples.append(sample)

print(new_train_samples)

# Create a new tf.Dataset for this cut down training set
new_train_ds = tf.data.Dataset.from_tensor_slices(new_train_samples)

new_train_ds = new_train_ds.map(tf_train_read_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

new_train_ds = new_train_ds.map(train_load_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

# Visualize some of the new training set
for image, target in new_train_ds.take(50):
  display_image_target([image, target])

"""## Band Analysis"""

bands = ['B1 (Aerosols)',
         'B2 (Blue)',
         'B3 (Green)',
         'B4 (Red)',
         'B5 (Red Edge 1)',
         'B6 (Red Edge 2)',
         'B7 (Red Edge 3)',
         'B8 (NIR)',
         'B8A (Red Edge 4)',
         'B11 (SWIR 1)',
         'B12 (SWIR 2)',
         'mean_2m_air_temperature',
         'minimum_2m_air_temperature',
         'maximum_2m_air_temperature',
         'dewpoint_2m_temperature',
         'total_precipitation',
         'surface_pressure',
         'mean_sea_level_pressure',
         'u_component_of_wind_10m',
         'v_component_of_wind_10m'
]

band_data = {}
for band in bands:
  band_data[band] = []

# Save band values from each image in training set
for image, target in tqdm(new_train_ds.take(len(new_train_samples)), total=len(new_train_samples)):
  for ind, band in enumerate(bands):
    band_data[band].append(image.numpy()[~np.isnan(image.numpy()[:, :, ind]), ind].flatten())

bands_colors = ['slategrey',
                'blue',
                'green',
                'red',
                'darkred',
                'maroon',
                'firebrick',
                'lightcoral',
                'indianred',
                'violet',
                'purple',
                'lightsteelblue',
                'royalblue',
                'orangered',
                'turquoise',
                'deepskyblue',
                'darkorange',
                'teal',
                'darkgrey',
                'lightgrey'
]

# Plot band histograms to help with normalization
plt.figure(figsize=(45, 40))
for ind, band in enumerate(bands):
  plt.subplot(5, 4, ind+1)
  plt.hist(np.concatenate(band_data[band]).ravel(), bins=200, color=bands_colors[ind])
  plt.title(band)

"""| Bands | min | max | 
| ----- | --- | --- |
| B1  (Aerosols) | 0 | 3000|
| B2  (Blue) | 0 | 4000|
| B3  (Green) | 0 | 4000|
| B4  (Red) | 0 | 4000|
| B5  (Red Edge 1) | 0 | 4000|
| B6  (Red Edge 2) | 0 | 5000|
| B7  (Red Edge 3) | 0 | 5000|
| B8  (NIR) | 0 | 5000|
| B8A (Red Edge 4) | 0 | 6000|
| B11 (SWIR 1) | 0 | 4000|
| B12 (SWIR 2) | 0 | 4000|
| mean_2m_air_temperature | 296.5 | 301.5|
| minimum_2m_air_temperature | 294 | 300.25|
| maximum_2m_air_temperature | 298 | 305.5|
| dewpoint_2m_temperature | 291 | 298|
| total_precipitation | 0 | 0.005|
| surface_pressure | 98500 | 102250|
| mean_sea_level_pressure | 101350 | 102050|
| u_component_of_wind_10m | -9 | 0|
| v_component_of_wind_10m | -2.5 | 2.5|
"""

# Observe Min/Max and store in dictionary
bands_norm = {
    'B1 (Aerosols)': (0, 3000),
    'B2 (Blue)': (0, 4000),
    'B3 (Green)': (0, 4000),
    'B4 (Red)': (0, 4000),
    'B5 (Red Edge 1)': (0, 4000),
    'B6 (Red Edge 2)': (0, 5000),
    'B7 (Red Edge 3)': (0, 5000),
    'B8 (NIR)': (0, 5000),
    'B8A (Red Edge 4)': (0, 6000),
    'B11 (SWIR 1)': (0, 4000),
    'B12 (SWIR 2)': (0, 4000),
    'mean_2m_air_temperature': (296.5, 301.5),
    'minimum_2m_air_temperature': (294, 300.25),
    'maximum_2m_air_temperature': (298, 305.5),
    'dewpoint_2m_temperature': (291, 298),
    'total_precipitation': (0, 0.005),
    'surface_pressure': (98500, 102250),
    'mean_sea_level_pressure': (101350, 102050),
    'u_component_of_wind_10m': (-9, 0),
    'v_component_of_wind_10m': (-2.5, 2.5)
}

"""# Data Transformation"""

# Function to normalize based on Min/Max while replacing NaN values
def normalize(image):
  for ind, band in enumerate(bands):
    min, max = bands_norm[band]
    image[~np.isnan(image[:, :, ind]), ind] = (image[~np.isnan(image[:, :, ind]), ind] - min) / (max - min)
    image[np.isnan(image[:, :, ind]), ind] = -1
  return image

# New data reading function to perform normaization
def train_read_norm_sample(data_path: str) -> tuple:
  path = data_path.numpy()
  image_path, target_path = path[0].decode('utf-8'), path[1].decode('utf-8')

  with rasterio.open(image_path) as src:
    img = np.transpose(src.read(), axes=(1, 2, 0)).astype(np.float32)

  img = normalize(img)

  with rasterio.open(target_path) as src:
    tgt = np.transpose(src.read(), axes=(1, 2, 0)).astype(np.float32)

  return (img, tgt)

# New loading function to call new reading function
@tf.function
def tf_train_read_norm_sample(data_path: str) -> dict:
  [image, target] = tf.py_function(train_read_norm_sample, [data_path], [tf.float32, tf.float32])

  image.set_shape((256, 256, 20))
  target.set_shape((256, 256, 1))

  return {'image': image, 'target': target}

# New test data reading function to perform normalization
def test_read_norm_sample(data_path: str) -> np.array:
  image_path = data_path.numpy().decode('utf-8')

  with rasterio.open(image_path) as src:
    img = np.transpose(src.read(), axes=(1, 2, 0)).astype(np.float32)

  img = normalize(img)

  return img

# New loading function to call new test reading function
@tf.function
def tf_test_read_norm_sample(data_path: str) -> dict:
  image = tf.py_function(test_read_norm_sample, [data_path], [tf.float32])

  image[0].set_shape((256, 256, 20))

  return {'image': image[0]}

# New function to perform augmentations of data since data size is small
@tf.function
def augment(img: tf.Tensor, tgt: tf.Tensor) -> tuple:
  rand = tf.random.uniform((), maxval=4, dtype=tf.int32)
  for i in range(rand):
    img = tf.image.rot90(img)
    tgt = tf.image.rot90(tgt)

  return img, tgt

# Create new tf.Dataset for the normalize, augmented data
shuffle(new_train_samples)

norm_train_ds = tf.data.Dataset.from_tensor_slices(new_train_samples)

norm_train_ds = norm_train_ds.map(tf_train_read_norm_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

norm_train_ds = norm_train_ds.map(train_load_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

# Apply data augmentation
norm_train_ds = norm_train_ds.map(augment, num_parallel_calls=tf.data.experimental.AUTOTUNE)

# Visualize the values of the Tensors to ensure they are in desired format
for image, target in norm_train_ds.take(10):
  print(image)

# Construct new normalize test tf.Dataset
norm_test_ds = tf.data.Dataset.from_tensor_slices(test_samples)

norm_test_ds = norm_test_ds.map(tf_test_read_norm_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

norm_test_ds = norm_test_ds.map(test_load_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

DATASET_SIZE = len(new_train_samples)
print(DATASET_SIZE)

# Split training data into validation set and training set
train_size = int(0.85 * DATASET_SIZE)
val_size = DATASET_SIZE - train_size
print(train_size)
print(val_size)

train_ds = norm_train_ds.take(train_size)
val_ds = norm_train_ds.skip(train_size)

"""# Building a Model"""

# Initialize model parameters
dropout_rate = 0.2
num_channels = 20

# Define a mostly standard UNet
input_size = (256, 256, num_channels)
initializer = 'he_normal'

# encoder
inputs = tf.keras.layers.Input(shape=input_size)
conv_en1 = tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(inputs)
conv_en1 = tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_en1)
max_pool_en1 = tf.keras.layers.MaxPooling2D(pool_size=(2, 2))(conv_en1)
max_pool_en1 = tf.keras.layers.Dropout(dropout_rate)(max_pool_en1)

conv_en2 = tf.keras.layers.Conv2D(128, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(max_pool_en1)
conv_en2 = tf.keras.layers.Conv2D(128, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_en2)
max_pool_en2 = tf.keras.layers.MaxPooling2D(pool_size=(2, 2))(conv_en2)
max_pool_en2 = tf.keras.layers.Dropout(dropout_rate)(max_pool_en2)

conv_en3 = tf.keras.layers.Conv2D(256, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(max_pool_en2)
conv_en3 = tf.keras.layers.Conv2D(256, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_en3)
max_pool_en3 = tf.keras.layers.MaxPooling2D(pool_size=(2, 2))(conv_en3)
max_pool_en3 = tf.keras.layers.Dropout(dropout_rate)(max_pool_en3)

conv_en4 = tf.keras.layers.Conv2D(512, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(max_pool_en3)
conv_en4 = tf.keras.layers.Conv2D(512, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_en4)
max_pool_en4 = tf.keras.layers.MaxPooling2D(pool_size=(2, 2))(conv_en4)
max_pool_en4 = tf.keras.layers.Dropout(dropout_rate)(max_pool_en4)

# latent layer
conv_mid = tf.keras.layers.Conv2D(1024, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(max_pool_en4)
conv_mid = tf.keras.layers.Conv2D(1024, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_mid)

# decoder
up_de1 = tf.keras.layers.Conv2D(512, (2, 2), activation='relu', padding='same', kernel_initializer=initializer)(tf.keras.layers.UpSampling2D(size=(2, 2))(conv_mid))
merge_de1 = tf.keras.layers.concatenate([conv_en4, up_de1], axis=3)
merge_de1 = tf.keras.layers.Dropout(dropout_rate)(merge_de1)
conv_de1 = tf.keras.layers.Conv2D(512, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(merge_de1)
conv_de1 = tf.keras.layers.Conv2D(512, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_de1)

up_de2 = tf.keras.layers.Conv2D(256, (2, 2), activation='relu', padding='same', kernel_initializer=initializer)(tf.keras.layers.UpSampling2D(size=(2, 2))(conv_de1))
merge_de2 = tf.keras.layers.concatenate([conv_en3, up_de2], axis=3)
merge_de2 = tf.keras.layers.Dropout(dropout_rate)(merge_de2)
conv_de2 = tf.keras.layers.Conv2D(256, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(merge_de2)
conv_de2 = tf.keras.layers.Conv2D(256, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_de2)

up_de3 = tf.keras.layers.Conv2D(128, (2, 2), activation='relu', padding='same', kernel_initializer=initializer)(tf.keras.layers.UpSampling2D(size=(2, 2))(conv_de2))
merge_de3 = tf.keras.layers.concatenate([conv_en2, up_de3], axis=3)
merge_de3 = tf.keras.layers.Dropout(dropout_rate)(merge_de3)
conv_de3 = tf.keras.layers.Conv2D(128, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(merge_de3)
conv_de3 = tf.keras.layers.Conv2D(128, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_de3)

up_de4 = tf.keras.layers.Conv2D(64, (2, 2), activation='relu', padding='same', kernel_initializer=initializer)(tf.keras.layers.UpSampling2D(size=(2, 2))(conv_de3))
merge_de4 = tf.keras.layers.concatenate([conv_en1, up_de4], axis=3)
merge_de4 = tf.keras.layers.Dropout(dropout_rate)(merge_de4)
conv_de4 = tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(merge_de4)
conv_de4 = tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same', kernel_initializer=initializer)(conv_de4)

outputs = tf.keras.layers.Conv2D(1, (1, 1), activation='sigmoid')(conv_de4)

# Build the model
unet = tf.keras.Model(inputs=inputs, outputs=outputs)

# Check the class distribution again
list(new_class_counts.values())

# Create class weights to help model learn
class_weights = list(new_class_counts.values())

# https://www.analyticsvidhya.com/blog/2020/10/improve-class-imbalance-class-weights/
class_weights[0] = 1 / (class_weights[0] * 2)
class_weights[1] = 1 / (class_weights[1] * 2)

# Defing training parameters
learning_rate = 1e-4
optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)

# Compile the model
unet.compile(optimizer=optimizer,
             loss=tfa.losses.SigmoidFocalCrossEntropy(),
             loss_weights=class_weights,
             metrics=['accuracy'])

"""# Training"""

# Set training parameters
EPOCHS = 50
TRAIN_LENGTH = train_size
BATCH_SIZE = 8
BUFFER_SIZE = 128
STEPS_PER_EPOCH = TRAIN_LENGTH//BATCH_SIZE
VAL_SUBSPLITS = 5
VALIDATION_STEPS = val_size//BATCH_SIZE//VAL_SUBSPLITS

# shuffle and repeat data 
train_dataset = train_ds.shuffle(BUFFER_SIZE).repeat().batch(BATCH_SIZE).prefetch(tf.data.experimental.AUTOTUNE)
val_dataset = val_ds.shuffle(BUFFER_SIZE).repeat().batch(BATCH_SIZE).prefetch(tf.data.experimental.AUTOTUNE)

# Create a callback for reducing learning rate
reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.1, patience=3, verbose=1, min_lr=1e-8)

# Train the model
model_history = unet.fit(train_dataset, epochs=EPOCHS,
                          steps_per_epoch=STEPS_PER_EPOCH,
                          validation_steps=VALIDATION_STEPS,
                          validation_data=val_dataset,
                          callbacks=reduce_lr)

# Plot the losses
plt.figure(figsize=(20, 12))
plt.plot(range(EPOCHS), model_history.history['loss'], 'r', label='Training loss')
plt.plot(range(EPOCHS), model_history.history['val_loss'], 'bo', label='Validation loss')
plt.title('Training and Validation Loss')
plt.xlabel('Epoch')
plt.ylabel('Loss Value')
plt.legend()
plt.show()

# Plot the accuracies
plt.figure(figsize=(20, 12))
plt.plot(range(EPOCHS), model_history.history['accuracy'], 'r', label='Training accuracy')
plt.plot(range(EPOCHS), model_history.history['val_accuracy'], 'bo', label='Validation accuracy')
plt.title('Training and Validation Accuracy')
plt.xlabel('Epoch')
plt.ylabel('Accuracy Value')
plt.legend()
plt.show()

"""# Testing"""

# Pass test data through the model
predictions = unet.predict(norm_test_ds.batch(BATCH_SIZE))

"""# Visualization"""

# Define a simple threshold to 
def threshold(target):
  return target >= .1

# Create new tf.Dataset that lines up with new shuffled data but not normalized for visualization
shuffled_ds = tf.data.Dataset.from_tensor_slices(new_train_samples)

shuffled_ds = shuffled_ds.map(tf_train_read_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

shuffled_ds = shuffled_ds.map(train_load_sample, num_parallel_calls=tf.data.experimental.AUTOTUNE)

# Just a check to see how model performs on training data
train_predictions = unet.predict(norm_train_ds.batch(BATCH_SIZE))
for ind, (image, target) in enumerate(shuffled_ds.take(50)):
  display_image_target([image, tf.constant(train_predictions[ind])])

# Apply the threshold to the training predictions
for ind, (image, target) in enumerate(shuffled_ds.take(50)):
  display_image_target([image, tf.constant(threshold(train_predictions[ind]))])

# See how model did on testing data without threshold
for ind, image in enumerate(test_ds.take(len(test_samples))):
  display_image_target([image, tf.constant(predictions[ind])])

# Visualize data with threshold
for ind, image in enumerate(test_ds.take(len(test_samples))):
  display_image_target([image, tf.constant(threshold(predictions[ind]))])