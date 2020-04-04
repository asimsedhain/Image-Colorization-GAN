
# Importing libraries
# problem in import
import tensorflow as tf
from tensorflow.keras.layers import Input, Reshape, Dropout, Dense, Flatten, BatchNormalization, Activation, ZeroPadding2D, Concatenate, Add
from tensorflow.keras.layers import LeakyReLU
from tensorflow.keras.layers import UpSampling2D, Conv2D
from tensorflow.keras.models import Sequential, Model, load_model
from tensorflow.keras.optimizers import Adam
import numpy as np
import cv2 as cv
import os 
import time
import matplotlib.pyplot as plt
import re
import pathlib

tf.compat.v1.enable_eager_execution(
    config=None, device_policy=None, execution_mode=None
)


# configration


"""Change the INITIAL_TRAINING variable to decide if model is to be loaded from memory or trained again."""
INITIAL_TRAINING = True



# Generation resolution - Must be square 
# Training data is also scaled to this.
# Note GENERATE_RES 4 or higher  will blow Google CoLab's memory and have not
# been tested extensivly.
GENERATE_RES = 4 # Generation resolution factor (1=32, 2=64, 3=96, 4=128, etc.)
GENERATE_SQUARE = 32 * GENERATE_RES # rows/cols (should be square)
IMAGE_CHANNELS = 3

# Preview image 
PREVIEW_ROWS = 4
PREVIEW_COLS = 7
PREVIEW_MARGIN = 16

# Size vector to generate images from
SEED_SIZE = 100

# Configuration
TRAINING_PATH = "../val_set"

DATA_PATH = "./"



# MODEL_PATH = os.path.join(DATA_PATH,"Models")
# GENERATOR_PATH = os.path.join(MODEL_PATH,"color_generator_5.h5")
# DISCRIMINATOR_PATH = os.path.join(MODEL_PATH,"color_discriminator_5.h5")

EPOCHS = 50
BATCH_SIZE = 128
BUFFER_SIZE = 60000


print(f"Will generate {GENERATE_SQUARE}px square images.")





def getDataset(path):
	train_path = pathlib.Path(path)
	list_ds = tf.data.Dataset.list_files(str(train/'*'))
	def parse_image(filename):
		image = tf.io.read_file(filename)
		image = tf.image.decode_jpeg(image)
		image = tf.image.convert_image_dtype(image, tf.float32)
		image = tf.image.rgb_to_yuv(image)
		image = tf.image.resize(image, [128, 128])
		return image
	img_ds = list_ds.map(parse_image)
	return img_ds.shuffle(BUFFER_SIZE).Batch(BATCH_SIZE)


train_dataset = getDataset(TRAINING_PATH)

# Helper method for saving an output file while training.
def save_images(cnt,dataset):

    sample_images = tf.convert_to_tensor([i.numpy() for i in dataset.take(16)])
    sample_images_input = tf.reshape(sample_images[:, :, :, 0],(16, 128, 128, 1))

    generated_images = generator.predict(sample_images_input)
    generated_images = tf.concat([sample_images_input, generated_images], 3) 
    generated_images = tf.image.yuv_to_rgb(generated_images)
    generated_images = generated_images.numpy()
    sample_images = tf.image.yuv_to_rgb(sample_images)
    sample_images = sample_images.numpy()
    

    fig = plt.figure(figsize=(20, 10))
    plt.tight_layout()
    for i in range(16):
        plt.subplot(4,8,(2*i) +1)
        plt.xticks([])
        plt.yticks([])
        plt.title("Ground Truth")
        plt.imshow(sample_images[i])
        plt.subplot(4,8,(2*i) + 2)
        plt.xticks([])
        plt.yticks([])
        plt.title("Model Generated")
        plt.imshow(generated_images[i])
    fig.savefig(os.path.join(DATA_PATH,f'output/test_{cnt}.png'), dpi =fig.dpi)
    plt.close(fig)



# generator code

def build_generator(channels=2, image_shape = (GENERATE_SQUARE, GENERATE_SQUARE, 1)):

	input_layer = Input(shape=image_shape)
	x = Conv2D(64, kernel_size=3,activation="relu", padding="same")(input_layer)
	x = BatchNormalization(momentum=0.8)(x)
	x = Activation("relu")(x)


	x = Conv2D(64,kernel_size=3, strides=1,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x_128_128 = Activation("relu")(x)

	x = Conv2D(128,kernel_size=3, strides=2,padding="same")(x_128_128)
	x = BatchNormalization(momentum=0.8)(x)
	x = Activation("relu")(x)

	x = Conv2D(128,kernel_size=3,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x_64_64 = Activation("relu")(x)

	x = Conv2D(256,kernel_size=3, strides=2,padding="same")(x_64_64)
	x = BatchNormalization(momentum=0.8)(x)
	x = Activation("relu")(x)

	x = Conv2D(256,kernel_size=3,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x = Activation("relu")(x)

	x = Conv2D(256,kernel_size=3,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x = Activation("relu")(x)



	# Output resolution, additional upsampling
	x = UpSampling2D(size=(2, 2))(x)
	x = Conv2D(128,kernel_size=3,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x = Concatenate()([x, x_64_64])
	x = Activation("relu")(x)

	x = Conv2D(128,kernel_size=3,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x = Activation("relu")(x)


	x = UpSampling2D(size=(2,2))(x)
	x = Conv2D(64,kernel_size=3,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x = Concatenate()([x, x_128_128])
	x = Activation("relu")(x)

	x = Conv2D(64,kernel_size=3,padding="same")(x)
	x = BatchNormalization(momentum=0.8)(x)
	x = Activation("relu")(x)

	# Final CNN layer
	x = Conv2D(2,kernel_size=3,padding="same")(x)
	output_layer = Activation("tanh")(x)

	return tf.keras.Model(inputs = input_layer, outputs=output_layer, name = "Generator")

# discrimator code

def build_discriminator(image_shape = (GENERATE_SQUARE, GENERATE_SQUARE, 2)):
	model = Sequential()

	model.add(Conv2D(32, kernel_size=3, strides=2, input_shape=image_shape, padding="same"))
	model.add(LeakyReLU(alpha=0.2))

	model.add(Dropout(0.25))
	model.add(Conv2D(64, kernel_size=3, strides=2, padding="same"))
	model.add(ZeroPadding2D(padding=((0,1),(0,1))))
	model.add(BatchNormalization(momentum=0.8))
	model.add(LeakyReLU(alpha=0.2))

	model.add(Dropout(0.25))
	model.add(Conv2D(64, kernel_size=3, strides=2, padding="same"))
	model.add(ZeroPadding2D(padding=((0,1),(0,1))))
	model.add(BatchNormalization(momentum=0.8))
	model.add(LeakyReLU(alpha=0.2))

	model.add(Dropout(0.25))
	model.add(Conv2D(64, kernel_size=3, strides=2, padding="same"))
	model.add(BatchNormalization(momentum=0.8))
	model.add(LeakyReLU(alpha=0.2))

	# model.add(Dropout(0.25))
	# model.add(Conv2D(128, kernel_size=3, strides=1, padding="same"))
	# model.add(BatchNormalization(momentum=0.8))
	# model.add(LeakyReLU(alpha=0.2))

	model.add(Dropout(0.25))
	model.add(Conv2D(128, kernel_size=3, strides=1, padding="same"))
	model.add(BatchNormalization(momentum=0.8))
	model.add(LeakyReLU(alpha=0.2))

	model.add(Dropout(0.25))
	model.add(Flatten())
	model.add(Dense(1, activation='sigmoid'))

	return model


# Checks if you want to continue training model from disk or start a new

if(INITIAL_TRAINING):
	print("Initializing Generator and Discriminator")
	generator = build_generator()
	discriminator = build_discriminator()
	print("Generator and Discriminator initialized")
# else:
# 	print("Loading model from memory")
# 	if os.path.isfile(GENERATOR_PATH):
# 		generator = tf.keras.models.load_model(GENERATOR_PATH)
# 		print("Generator loaded")
# 	else:
# 		assert(os.path.isfile(GENERATOR_PATH), True)
# 		print("No generator file found")
# 	if os.path.isfile(DISCRIMINATOR_PATH):
		
# 		discriminator = tf.keras.models.load_model(DISCRIMINATOR_PATH)
# 		print("Discriminator loaded")
# 	else:
# 		assert(os.path.isfile(GENERATOR_PATH), True)
# 		print("No discriminator file found")
		





# This method returns a helper function to compute cross entropy loss
cross_entropy = tf.keras.losses.BinaryCrossentropy(from_logits=True)
mean_absolute = tf.keras.losses.MeanAbsoluteError()

def discriminator_loss(real_output, fake_output):
	real_loss = cross_entropy(tf.ones_like(real_output), real_output)
	fake_loss = cross_entropy(tf.zeros_like(fake_output), fake_output)
	total_loss = real_loss + fake_loss
	return total_loss

def generator_loss(fake_output, real_images, gen_images ):
	return cross_entropy(tf.ones_like(fake_output), fake_output) + 100*mean_absolute(real_images, gen_images)

generator_optimizer = tf.keras.optimizers.Adam(2e-4,0.5)
discriminator_optimizer = tf.keras.optimizers.Adam(2e-4,0.5)

@tf.function
def train_step(images):
  
	seed = tf.reshape(images[:,:, :, 0], (images.shape[0], GENERATE_SQUARE, GENERATE_SQUARE, 1))
	real = images[:,:, :, 1:3]

	with tf.GradientTape() as gen_tape, tf.GradientTape() as disc_tape:
		generated_images = generator(seed, training=True)
		real_output = discriminator(real, training=True)
		fake_output = discriminator(generated_images, training=True)

	gen_loss = generator_loss(fake_output, real, generated_images)
	disc_loss = discriminator_loss(real_output, fake_output)


	gradients_of_generator = gen_tape.gradient(gen_loss, generator.trainable_variables)
	gradients_of_discriminator = disc_tape.gradient(disc_loss, discriminator.trainable_variables)

	generator_optimizer.apply_gradients(zip(gradients_of_generator, generator.trainable_variables))
	discriminator_optimizer.apply_gradients(zip(gradients_of_discriminator, discriminator.trainable_variables))
	return gen_loss,disc_loss

def train(dataset, epochs):
	start = time.time()
	
	for epoch in range(epochs):
		epoch_start = time.time()

		gen_loss_list = []
		disc_loss_list = []

		for image_batch in dataset:
			t = train_step(image_batch)
			gen_loss_list.append(t[0])
			disc_loss_list.append(t[1])

		g_loss = sum(gen_loss_list) / len(gen_loss_list)
		d_loss = sum(disc_loss_list) / len(disc_loss_list)

		epoch_elapsed = time.time()-epoch_start
		print (f'Epoch {epoch+1}, gen loss={g_loss},disc loss={d_loss}, {(epoch_elapsed)}')
		# save_images(epoch,dataset)
		# if(epoch%5==0):
		# 	print(f"Saving Model for epoch {epoch}")
		# 	generator.save(os.path.join(MODEL_PATH,f"color_generator_{epoch}.h5"))
		# 	discriminator.save(os.path.join(MODEL_PATH,f"color_discriminator_{epoch}.h5"))

	elapsed = time.time()-start
	print (f'Training time: {(elapsed)}')

train(train_dataset, 100)





# saving the model to disk
MODEL_PATH = os.path.join(DATA_PATH,"Models")
generator.save(os.path.join(MODEL_PATH,"color_generator_main.h5"))
discriminator.save(os.path.join(MODEL_PATH,"color_discriminator_main.h5"))












