
# Importing libraries

import tensorflow as tf
from tensorflow.keras.layers import Input, Reshape, Dropout, Dense, Flatten, BatchNormalization, Activation, ZeroPadding2D, Concatenate, Add
from tensorflow.keras.layers import LeakyReLU
from tensorflow.keras.layers import UpSampling2D, Conv2D
from tensorflow.keras.models import Sequential, Model, load_model
from tensorflow.train import AdamOptimizer as Adam
import numpy as np
import os 
import time
import cv2 as cv

import horovod.tensorflow as hvd


# Need to use "Agg" for machines without a display. Or it wil result in segmentation fault
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt



# Helper libraries
from models import build_discriminator
from models import build_generator
from models import discriminator_loss
from models import generator_loss
from utils import get_dataset
from utils import save_images



# Horovod: initialize Horovod.
hvd.init()

# Horovod: pin GPU to be used to process local rank (one GPU per process)
config = tf.ConfigProto()
config.gpu_options.visible_device_list = str(hvd.local_rank())

tf.enable_eager_execution(config=config)


# Configration

# Training data directory
TRAINING_DATA_PATH = "../test"

# All the output and models will be saved inside the checkpoint path
CHECKPOINT_PATH = "./"

# Sample images will be stored in the output path
OUTPUT_PATH = os.path.join(CHECKPOINT_PATH, "output") 

# Path for the model. It is inside the checkpoint directory
MODEL_PATH = os.path.join(CHECKPOINT_PATH,"Models")

# If INITIAL_TRAINING is set to False, generator and discriminator will be loaded from the following path
GENERATOR_PATH_PRE = os.path.join(MODEL_PATH,"color_generator_main.h5")
DISCRIMINATOR_PATH_PRE = os.path.join(MODEL_PATH,"color_discriminator_main.h5")

# Path for the final models to be saved to after training
GENERATOR_PATH_FINAL = os.path.join(MODEL_PATH,"color_generator_final.h5")
DISCRIMINATOR_PATH_FINAL = os.path.join(MODEL_PATH,"color_discriminator_final.h5")


# Change the INITIAL_TRAINING variable to decide if model is to be loaded from memory or trained again.
INITIAL_TRAINING = True

# Size of the image. The input data will also be scaled to this amount.
GENERATE_SQUARE = 128


STEPS = 10000
BATCH_SIZE = 32
BUFFER_SIZE = 60000




print(f"Will generate {GENERATE_SQUARE}px square images.")




print(f"Images being loaded from {TRAINING_DATA_PATH}")

train_dataset = get_dataset(TRAINING_DATA_PATH, BUFFER_SIZE, BATCH_SIZE)
print(f"Images loaded from {TRAINING_DATA_PATH}")






# Checks if you want to continue training model from disk or start a new

if(INITIAL_TRAINING):
	print("Initializing Generator and Discriminator")
	generator = build_generator(image_shape=(GENERATE_SQUARE, GENERATE_SQUARE, 1))
	discriminator = build_discriminator(image_shape=(GENERATE_SQUARE, GENERATE_SQUARE, 2))
	print("Generator and Discriminator initialized")
else:
	print("Loading model from memory")
	if os.path.isfile(GENERATOR_PATH_PRE):
		generator = tf.keras.models.load_model(GENERATOR_PATH_PRE)
		print("Generator loaded")
	else:
		print("No generator file found")
	if os.path.isfile(DISCRIMINATOR_PATH_PRE):
		
		discriminator = tf.keras.models.load_model(DISCRIMINATOR_PATH_PRE)
		print("Discriminator loaded")
	else:
		print("No discriminator file found")
		






# scaling learning rate by number of GPUs.
generator_optimizer = Adam(2e-4 * hvd.size(),0.5)
discriminator_optimizer = Adam(2e-4 * hvd.size(),0.5)


def train_step(images):
  
	seed = tf.reshape(images[:,:, :, 0], (images.shape[0], GENERATE_SQUARE, GENERATE_SQUARE, 1))
	real = images[:,:, :, 1:3]
	
	with tf.GradientTape() as gen_tape, tf.GradientTape() as disc_tape:
		generated_images = generator(seed, training=True)
		real_output = discriminator(real, training=True)
		fake_output = discriminator(generated_images, training=True)

	gen_loss = generator_loss(fake_output, real, generated_images)
	disc_loss = discriminator_loss(real_output, fake_output)

	gen_tape = hvd.DistributedGradientTape(gen_tape)
	disc_tape = hvd.DistributedGradientTape(disc_tape)


	gradients_of_generator = gen_tape.gradient(gen_loss, generator.trainable_variables)
	gradients_of_discriminator = disc_tape.gradient(disc_loss, discriminator.trainable_variables)

	generator_optimizer.apply_gradients(zip(gradients_of_generator, generator.trainable_variables))
	discriminator_optimizer.apply_gradients(zip(gradients_of_discriminator, discriminator.trainable_variables))


		


	return gen_loss,disc_loss

def train(dataset, epochs):
	start = time.time()
	last_time = time.time()
	for batch, image_batch in enumerate(dataset.take(epochs//hvd.size())):
		if(batch==0):
			hvd.broadcast_variables(generator.variables, root_rank=0)
			hvd.broadcast_variables(discriminator.variables, root_rank=0)

		g_loss, d_loss = train_step(image_batch)
		
		if batch % 10 == 0 and hvd.local_rank() == 0:
			print (f'batch: {batch}, gen loss={g_loss},disc loss={d_loss}, {(time.time()-last_time)}')
			last_time= time.time()
		

		#save_images(OUTPUT_PATH, epoch,dataset, generator)
		# if(batch%10==0):
			# print(f"Saving Model for Step {epoch}")
			#generator.save(os.path.join(MODEL_PATH,f"color_generator_{epoch}.h5"))
			#discriminator.save(os.path.join(MODEL_PATH,f"color_discriminator_{epoch}.h5"))
			# save_images(OUTPUT_PATH, epoch,dataset, generator)


	elapsed = time.time()-start
	print (f'Training time: {(elapsed)}')

print("Starting Training")

train(train_dataset, STEPS)


print("Training Finished")


# saving the model to disk

# print("Saving Models")
# generator.save(GENERATOR_PATH_FINAL)
# discriminator.save(DISCRIMINATOR_PATH_FINAL)













