# -*- coding: utf-8 -*-
"""vae.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/18pWjhMG_j2o1kj6gUFN4-WzU0SfvtGj_

# Stardard VAE

100 次训练生成图片，ELBO 约 -118

* reparameterize
   
  计算 z=$\mu + \sigma \odot \varepsilon$
* log_normal_pdf

  计算 log p(x|z) = $\sum{ (sample-\mu)^2 \over {2 \sigma^2}}+\log(\sqrt{2\pi}\ \sigma )$
"""

import tensorflow as tf


class VAE(tf.keras.Model):
    def __init__(self, latent_dim):
        super(VAE, self).__init__()
        self.latent_dim = latent_dim
        
        # Encoder NN
        self.encoder = tf.keras.Sequential(
          [
            tf.keras.layers.InputLayer(input_shape=(28, 28, 1)),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dense(64),
            tf.keras.layers.Dense(latent_dim + latent_dim),
          ]
        )

        # Decoder NN
        self.decoder = tf.keras.Sequential(
          [
            tf.keras.layers.InputLayer(input_shape=(latent_dim)),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dense(128),
            tf.keras.layers.Dense(784),
            tf.keras.layers.Reshape(target_shape=(28, 28, 1)),
          ]
        )

    # sample 
    @tf.function
    def sample(self, eps=None):
        if eps is None:
            eps = tf.random.normal(shape=(100, self.latent_dim))
        return self.decode(eps, apply_sigmoid=True)

    # encode  
    def encode(self, x):
        mean, logvar = tf.split(self.encoder(x), num_or_size_splits=2, axis=1)
        return mean, logvar

    # reparameterize
    def reparameterize(self, mean, logvar):
        eps = tf.random.normal(shape=mean.shape)
        return eps * tf.exp(logvar * .5) + mean
    
    # decode
    def decode(self, z, apply_sigmoid=False):
        logits = self.decoder(z)
        if apply_sigmoid:
            probs = tf.sigmoid(logits)
            return probs
        return logits

# 优化器
optimizer = tf.keras.optimizers.Adam(1e-4)

# 计算 log p(x|z) 
def log_normal_pdf(sample, mean, logvar, raxis=1):
  log2pi = tf.math.log(2. * np.pi)
  return tf.reduce_sum(
      -.5 * ((sample - mean) ** 2. * tf.exp(-logvar) + logvar + log2pi),
      axis=raxis)

# 损失函数 
def compute_loss(model, x):
  mean, logvar = model.encode(x)
  z = model.reparameterize(mean, logvar)
  x_logit = model.decode(z)
  cross_ent = tf.nn.sigmoid_cross_entropy_with_logits(logits=x_logit, labels=x)
  logpx_z = -tf.reduce_sum(cross_ent, axis=[1, 2, 3])
  logpz = log_normal_pdf(z, 0., 0.)
  logqz_x = log_normal_pdf(z, mean, logvar)
  return -tf.reduce_mean(logpx_z + logpz - logqz_x)


# 梯度下降
@tf.function
def train_step(model, x, optimizer):
  """Executes one training step and returns the loss.

  This function computes the loss and gradients, and uses the latter to
  update the model's parameters.
  """
  with tf.GradientTape() as tape:
    loss = compute_loss(model, x)
  gradients = tape.gradient(loss, model.trainable_variables)
  optimizer.apply_gradients(zip(gradients, model.trainable_variables))

# 生成次数
epochs = 100

# 隐藏层维度（包括均值和方差）
latent_dim = 5
num_examples_to_generate = 16

# 保持随机维度不变，以便于查看生成效果的优化过程
random_vector_for_generation = tf.random.normal(
    shape=[num_examples_to_generate, latent_dim])
model = VAE(latent_dim)

# 生成并保存图像
def generate_and_save_images(model, epoch, test_sample):
  # 1. encode 拿到均值和方差
  mean, logvar = model.encode(test_sample)

  # 2. 获得隐藏层，采样
  z = model.reparameterize(mean, logvar)

  # 3. 采样
  predictions = model.sample(z)
  fig = plt.figure(figsize=(4, 4))

  # 生成图片
  for i in range(predictions.shape[0]):
    plt.subplot(4, 4, i + 1)
    plt.imshow(predictions[i, :, :, 0], cmap='gray')
    plt.axis('off')

  # tight_layout minimizes the overlap between 2 sub-plots
  # 保存并显示图片
  plt.savefig('image_at_epoch_{:04d}.png'.format(epoch))
  plt.show()

# !pip install -q tensorflow-probability

# # to generate gifs
# !pip install -q imageio
# !pip install -q git+https://github.com/tensorflow/docs

from IPython import display

import glob
import imageio
import matplotlib.pyplot as plt
import numpy as np
import PIL
import tensorflow as tf
import tensorflow_probability as tfp
import time

(train_images, _), (test_images, _) = tf.keras.datasets.mnist.load_data()

def preprocess_images(images):
  images = images.reshape((images.shape[0], 28, 28, 1)) / 255.
  return np.where(images > .5, 1.0, 0.0).astype('float32')

train_images = preprocess_images(train_images)
test_images = preprocess_images(test_images)

train_size = 60000
batch_size = 32
test_size = 10000

train_dataset = (tf.data.Dataset.from_tensor_slices(train_images)
                 .shuffle(train_size).batch(batch_size))
test_dataset = (tf.data.Dataset.from_tensor_slices(test_images)
                .shuffle(test_size).batch(batch_size))

# Pick a sample of the test set for generating output images
assert batch_size >= num_examples_to_generate
for test_batch in test_dataset.take(1):
  test_sample = test_batch[0:num_examples_to_generate, :, :, :]
  
generate_and_save_images(model, 0, test_sample)

for epoch in range(1, epochs + 1):
  start_time = time.time()
  for train_x in train_dataset:
    train_step(model, train_x, optimizer)
  end_time = time.time()

  loss = tf.keras.metrics.Mean()
  for test_x in test_dataset:
    loss(compute_loss(model, test_x))
  elbo = -loss.result()
  display.clear_output(wait=False)
  print('Epoch: {}, Test set ELBO: {}, time elapse for current epoch: {}'
        .format(epoch, elbo, end_time - start_time))
  generate_and_save_images(model, epoch, test_sample)
