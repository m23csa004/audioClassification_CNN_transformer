# -*- coding: utf-8 -*-
"""dl assign2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Nn8dnAFFl0C5eJv5ZNGB73eLIdX2l_Nq

**Data Loading and Preprocessing**
"""

from google.colab import drive
drive.mount('/content/drive')

# Installing the requirements
print('Installing Requirements... ',end='')
!pip install lightning
print('Done')

# Importing Libraries
print('Importing Libraries... ',end='')
import os
from pathlib import Path
import pandas as pd
import torchaudio
import zipfile
from torchaudio.transforms import Resample
import IPython.display as ipd
from matplotlib import pyplot as plt
from tqdm import tqdm
import pytorch_lightning as pl
from torch.utils.data import Dataset, DataLoader
import torch
print('Done')

# Download data
print('Downlading data... ', end='')
# Your code here
print('Done')

# Extract data
with zipfile.ZipFile("/content/drive/MyDrive/Archive.zip", 'r') as zip_ref:
    zip_ref.extractall("/content/")

# Loading dataset
path = Path('/content/')
df = pd.read_csv('/content/meta/esc50.csv')

# Getting list of raw audio files
wavs = list(path.glob('audio/*'))  # List all audio files in the 'audio' directory using pathlib.Path.glob

# Visualizing data
waveform, sample_rate = torchaudio.load(wavs[0])  # Load the waveform and sample rate of the first audio file using torchaudio

print("Shape of waveform: {}".format(waveform.size()))  # Print the shape of the waveform tensor
print("Sample rate of waveform: {}".format(sample_rate))  # Print the sample rate of the audio file

# Plot the waveform using matplotlib
plt.figure()
plt.plot(waveform.t().numpy())  # Transpose and convert the waveform tensor to a NumPy array for plotting

# Display the audio using IPython.display.Audio
ipd.Audio(waveform, rate=sample_rate)  # Create an interactive audio player for the loaded waveform

class CustomDataset(Dataset):
    def __init__(self, dataset, **kwargs):
        # Initialize CustomDataset object with relevant parameters
        # dataset: "train", "val", or "test"
        # kwargs: Additional parameters like data directory, dataframe, folds, etc.

        # Extract parameters from kwargs
        self.data_directory = kwargs["data_directory"]
        self.data_frame = kwargs["data_frame"]
        self.validation_fold = kwargs["validation_fold"]
        self.testing_fold = kwargs["testing_fold"]
        self.esc_10_flag = kwargs["esc_10_flag"]
        self.file_column = kwargs["file_column"]
        self.label_column = kwargs["label_column"]
        self.sampling_rate = kwargs["sampling_rate"]
        self.new_sampling_rate = kwargs["new_sampling_rate"]
        self.sample_length_seconds = kwargs["sample_length_seconds"]

        # Filter dataframe based on esc_10_flag and data_type
        if self.esc_10_flag:
            self.data_frame = self.data_frame.loc[self.data_frame['esc10'] == True]

        if dataset == "train":
            self.data_frame = self.data_frame.loc[
                (self.data_frame['fold'] != self.validation_fold) & (self.data_frame['fold'] != self.testing_fold)]
        elif dataset == "val":
            self.data_frame = self.data_frame.loc[self.data_frame['fold'] == self.validation_fold]
        elif dataset == "test":
            self.data_frame = self.data_frame.loc[self.data_frame['fold'] == self.testing_fold]

        # Get unique categories from the filtered dataframe
        self.categories = sorted(self.data_frame[self.label_column].unique())

        # Initialize lists to hold file names, labels, and folder numbers
        self.file_names = []
        self.labels = []

        # Initialize dictionaries for category-to-index and index-to-category mapping
        self.category_to_index = {}
        self.index_to_category = {}

        for i, category in enumerate(self.categories):
            self.category_to_index[category] = i
            self.index_to_category[i] = category

        # Populate file names and labels lists by iterating through the dataframe
        for ind in tqdm(range(len(self.data_frame))):
            row = self.data_frame.iloc[ind]
            file_path = self.data_directory / "audio" / row[self.file_column]
            self.file_names.append(file_path)
            self.labels.append(self.category_to_index[row[self.label_column]])

        self.resampler = torchaudio.transforms.Resample(self.sampling_rate, self.new_sampling_rate)

        # Window size for rolling window sample splits (unfold method)
        if self.sample_length_seconds == 2:
            self.window_size = self.new_sampling_rate * 2
            self.step_size = int(self.new_sampling_rate * 0.75)
        else:
            self.window_size = self.new_sampling_rate
            self.step_size = int(self.new_sampling_rate * 0.5)

    def __getitem__(self, index):
        # Split audio files with overlap, pass as stacked tensors tensor with a single label
        path = self.file_names[index]
        audio_file = torchaudio.load(path, format=None, normalize=True)
        audio_tensor = self.resampler(audio_file[0])
        splits = audio_tensor.unfold(1, self.window_size, self.step_size)
        samples = splits.permute(1, 0, 2)
        return samples, self.labels[index]

    def __len__(self):
        return len(self.file_names)

class CustomDataModule(pl.LightningDataModule):
    def __init__(self, **kwargs):
        # Initialize the CustomDataModule with batch size, number of workers, and other parameters
        super().__init__()
        self.batch_size = kwargs["batch_size"]
        self.num_workers = kwargs["num_workers"]
        self.data_module_kwargs = kwargs

    def setup(self, stage=None):
        # Define datasets for training, validation, and testing during Lightning setup

        # If in 'fit' or None stage, create training and validation datasets
        if stage == 'fit' or stage is None:
            self.training_dataset = CustomDataset(dataset="train", **self.data_module_kwargs)
            self.validation_dataset = CustomDataset(dataset="val", **self.data_module_kwargs)

        # If in 'test' or None stage, create testing dataset
        if stage == 'test' or stage is None:
            self.testing_dataset = CustomDataset(dataset="test", **self.data_module_kwargs)

    def train_dataloader(self):
        # Return DataLoader for training dataset
        return DataLoader(self.training_dataset,
                          batch_size=self.batch_size,
                          shuffle=True,
                          collate_fn=self.collate_function,
                          num_workers=self.num_workers)

    def val_dataloader(self):
        # Return DataLoader for validation dataset
        return DataLoader(self.validation_dataset,
                          batch_size=self.batch_size,
                          shuffle=False,
                          collate_fn=self.collate_function,
                          num_workers=self.num_workers)

    def test_dataloader(self):
        # Return DataLoader for testing dataset
        return DataLoader(self.testing_dataset,
                          batch_size=32,
                          shuffle=False,
                          collate_fn=self.collate_function,
                          num_workers=self.num_workers)

    def collate_function(self, data):
        """
        Collate function to process a batch of examples and labels.

        Args:
            data: a tuple of 2 tuples with (example, label) where
                example are the split 1 second sub-frame audio tensors per file
                label = the label

        Returns:
            A list containing examples (concatenated tensors) and labels (flattened tensor).
        """
        examples, labels = zip(*data)
        examples = torch.stack(examples)
        examples =examples.reshape(examples.size(0),1,-1)
        labels = torch.flatten(torch.tensor(labels))

        return [examples, labels]

# Data Setup
test_samp = 1 #Do not change this!! """
valid_samp = 2 # Use any value ranging from 2 to 5 for k-fold validation (valid_fold)
batch_size = 32 # Free to change
num_workers = 0 # Free to change
custom_data_module = CustomDataModule(batch_size=batch_size,
                                      num_workers=num_workers,
                                      data_directory=path,
                                      data_frame=df,
                                      validation_fold=valid_samp,
                                      testing_fold=test_samp,  # set to 0 for no test set
                                      esc_10_flag=True,
                                      file_column='filename',
                                      label_column='category',
                                      sampling_rate=44100,
                                      new_sampling_rate=16000,  # new sample rate for input
                                      sample_length_seconds=1  # new length of input in seconds
                                      )

custom_data_module.setup()

# Data Exploration
print('Class Label: ', custom_data_module.training_dataset[0][1])  # this prints the class label
print('Shape of data sample tensor: ', custom_data_module.training_dataset[0][0].shape)  # this prints the shape of the sample (Frames, Channel, Features)

# Dataloader(s)
x = next(iter(custom_data_module.train_dataloader()))
y = next(iter(custom_data_module.val_dataloader()))
z = next(iter(custom_data_module.test_dataloader()))
print('Train Dataloader:')
print(x)
print('Validation Dataloader:')
print(y)
print('Test Dataloader:')
print(z)

"""

---

"""

print('Shape of x: ',x[0][0].shape)

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchsummary import summary

# Assuming custom_data_module contains your custom dataset and dataloaders

# Define your Conv1DClassifier model
class Conv1DClassifier(nn.Module):
    def __init__(self, num_classes):
        super(Conv1DClassifier, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=32, kernel_size=11, stride=5, padding=5)
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=9, stride=5, padding=4)
        self.conv3 = nn.Conv1d(in_channels=64, out_channels=128, kernel_size=7, stride=3, padding=3)
        self.conv4 = nn.Conv1d(in_channels=128, out_channels=256, kernel_size=5, stride=2, padding=2)
        self.conv5 = nn.Conv1d(in_channels=256, out_channels=512, kernel_size=3, stride=1, padding=1)

        self.pool = nn.MaxPool1d(kernel_size=3, stride=3)
        #val = 512*(144000/243)      #this will be used if stride =1,here 243= (3^5)
        self.fc1 = nn.Linear(2048, 128)
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = self.pool(x)
        x = F.relu(self.conv2(x))
        x = self.pool(x)
        x = F.relu(self.conv3(x))
        x = self.pool(x)
        x = F.relu(self.conv4(x))
        x = self.pool(x)
        x = F.relu(self.conv5(x))
        x = self.pool(x)
        x = torch.flatten(x, 1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x

# Define the number of classes
num_classes = 10

# Instantiate the model and move it to GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = Conv1DClassifier(num_classes).to(device)

# Print model summary
summary(model, (1, 144000))

# Define loss function
criterion = nn.CrossEntropyLoss()

# Define optimizer
optimizer = optim.Adam(model.parameters(), lr=0.01)

# Define number of epochs
num_epochs = 100

"""WandB"""

!pip install wandb -qU

import wandb
wandb.login()

#wandb.init(project="dl_assignment_2")
wandb.init(project='dl_assignment_2', name='training_run')

# Training loop
for epoch in range(num_epochs):
    model.train()  # Set the model to training mode
    running_loss = 0.0
    correct = 0
    total = 0

    for data in custom_data_module.train_dataloader():
        inputs, labels = data[0].to(device), data[1].to(device)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

    epoch_loss = running_loss / len(custom_data_module.train_dataloader())
    epoch_accuracy = 100 * correct / total

    # Log loss and accuracy with WandB
    wandb.log({"Train Loss": epoch_loss, "Train Accuracy": epoch_accuracy}, step=epoch)

    print(f"Epoch [{epoch + 1}/{num_epochs}], Loss: {epoch_loss:.4f}, Accuracy: {epoch_accuracy:.2f}%")


# Calculate accuracy on the training set
model.eval()  # Set the model to evaluation mode
correct = 0
total = 0

with torch.no_grad():
    for data in custom_data_module.train_dataloader():
        inputs, labels = data[0].to(device), data[1].to(device)  # Move data to GPU if available
        outputs = model(inputs)
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

train_accuracy = 100 * correct / total

# Log final training accuracy with WandB
wandb.log({"Final Train Accuracy": train_accuracy})

print(f"Accuracy on the training set: {train_accuracy:.2f}%")

wandb.finish()  # Finish WandB logging at the end of training

# Calculate accuracy on the validation set
correct = 0
total = 0

with torch.no_grad():
    for data in custom_data_module.val_dataloader():
        inputs, labels = data[0].to(device), data[1].to(device)  # Move data to GPU if available
        outputs = model(inputs)
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

val_accuracy = 100 * correct / total
print(f"Accuracy on the validation set: {val_accuracy:.2f}%")

# Calculate accuracy on the test set
correct = 0
total = 0

with torch.no_grad():
    for data in custom_data_module.test_dataloader():
        inputs, labels = data[0].to(device), data[1].to(device)  # Move data to GPU if available
        outputs = model(inputs)
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

test_accuracy = 100 * correct / total
print(f"Accuracy on the test set: {test_accuracy:.2f}%")

"""Confusion,Roc plots"""

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, roc_auc_score, roc_curve, auc
import matplotlib.pyplot as plt

# Set the model to evaluation mode
model.eval()

# Lists to store true labels and predicted labels
true_labels = []
predicted_probs = []

with torch.no_grad():
    for data in custom_data_module.test_dataloader():
        inputs, labels = data[0].to(device), data[1].to(device)
        outputs = model(inputs)
        _, predicted = torch.max(outputs, 1)

        true_labels.extend(labels.cpu().numpy())
        predicted_probs.extend(torch.softmax(outputs, dim=1).cpu().numpy())

# Convert lists to numpy arrays
true_labels = np.array(true_labels)
predicted_probs = np.array(predicted_probs)

# Confusion Matrix
conf_matrix = confusion_matrix(true_labels, np.argmax(predicted_probs, axis=1))
print("Confusion Matrix:")
print(conf_matrix)

# Classification Report (includes precision, recall, and F1-score)
class_report = classification_report(true_labels, np.argmax(predicted_probs, axis=1))
print("Classification Report:")
print(class_report)

# AUC-ROC Curve
num_classes = 10
fpr = dict()
tpr = dict()
roc_auc = dict()

# Compute ROC curve and ROC area for each class
for i in range(num_classes):
    fpr[i], tpr[i], _ = roc_curve((true_labels == i).astype(int), predicted_probs[:, i])
    roc_auc[i] = auc(fpr[i], tpr[i])

# Plot ROC curve
plt.figure(figsize=(10, 6))
for i in range(num_classes):
    plt.plot(fpr[i], tpr[i], label=f'Class {i} (AUC = {roc_auc[i]:.2f})')

plt.plot([0, 1], [0, 1], linestyle='--', color='black', label='Random')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('Receiver Operating Characteristic (ROC) Curve')
plt.legend()
plt.show()



















"""Architecture  2"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import pytorch_lightning as pl
from torch.utils.data import DataLoader

# Define the Convolutional Base
class ConvolutionalBase(nn.Module):
    def __init__(self):
        super(ConvolutionalBase, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=32, kernel_size=11, stride=5, padding=5)
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=9, stride=5, padding=4)
        self.conv3 = nn.Conv1d(in_channels=64, out_channels=128, kernel_size=7, stride=3, padding=3)
        self.conv4 = nn.Conv1d(in_channels=128, out_channels=256, kernel_size=5, stride=2, padding=2)
        self.conv5 = nn.Conv1d(in_channels=256, out_channels=512, kernel_size=3, stride=1, padding=1)
        self.pool = nn.MaxPool1d(kernel_size=3, stride=3)

    def forward(self, x):
        # Input dimension: (batch_size, 1, 144000)
        x = F.relu(self.conv1(x))
        # Dimension after conv1: (batch_size, 32, 28800)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 32, 9600)
        x = F.relu(self.conv2(x))
        # Dimension after conv2: (batch_size, 64, 1920)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 64, 640)
        x = F.relu(self.conv3(x))
        # Dimension after conv3: (batch_size, 128, 214)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 128, 71)
        x = F.relu(self.conv4(x))
        # Dimension after conv4: (batch_size, 256, 36)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 256, 12)
        x = F.relu(self.conv5(x))
        # Dimension after conv5: (batch_size, 512, 12)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 512, 4)
        return x

class ConvolutionalBase1(nn.Module):
    def __init__(self, embed_size):
        super(ConvolutionalBase1, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=32, kernel_size=11, stride=5, padding=5)
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=9, stride=5, padding=4)
        self.conv3 = nn.Conv1d(in_channels=64, out_channels=128, kernel_size=7, stride=3, padding=3)
        self.conv4 = nn.Conv1d(in_channels=128, out_channels=256, kernel_size=5, stride=2, padding=2)
        self.conv5 = nn.Conv1d(in_channels=256, out_channels=512, kernel_size=3, stride=1, padding=1)
        self.pool = nn.MaxPool1d(kernel_size=3, stride=3)
        self.embed_size = embed_size

    def forward(self, x):
        # Input dimension: (batch_size, 1, 144000)
        x = F.relu(self.conv1(x))
        # Dimension after conv1: (batch_size, 32, 28800)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 32, 9600)
        x = F.relu(self.conv2(x))
        # Dimension after conv2: (batch_size, 64, 1920)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 64, 640)
        x = F.relu(self.conv3(x))
        # Dimension after conv3: (batch_size, 128, 214)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 128, 71)
        x = F.relu(self.conv4(x))
        # Dimension after conv4: (batch_size, 256, 36)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 256, 12)
        x = F.relu(self.conv5(x))
        # Dimension after conv5: (batch_size, 512, 12)
        x = self.pool(x)
        # Dimension after pooling: (batch_size, 512, 4)

        # Reshape the tensor to match the expected input shape for the Transformer
        x = x.permute(0, 2, 1)  # Permute dimensions to (batch_size, seq_length, channels)
        x = x.view(-1, x.size(1), self.embed_size)  # Reshape to (batch_size, seq_length, embed_size)
        return x



# Define MultiHead Self-Attention Block
class MultiHeadSelfAttention(nn.Module):
    def __init__(self, d_model, num_heads):
        super(MultiHeadSelfAttention, self).__init__()
        self.num_heads = num_heads
        self.d_model = d_model
        assert d_model % num_heads == 0
        self.depth = d_model // num_heads
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_out = nn.Linear(d_model, d_model)

    def forward(self, query, key, value):
        batch_size = query.shape[0]
        query = query
        key = self.W_k(key)
        value = self.W_v(value)
        query = query.view(batch_size, -1, self.num_heads, self.depth).transpose(1, 2)
        key = key.view(batch_size, -1, self.num_heads, self.depth).transpose(1, 2)
        value = value.view(batch_size, -1, self.num_heads, self.depth).transpose(1, 2)
        scores = torch.matmul(query, key.transpose(-2, -1)) / torch.sqrt(torch.tensor(self.depth, dtype=torch.float32))
        attention_weights = F.softmax(scores, dim=-1)
        attention_output = torch.matmul(attention_weights, value)
        attention_output = attention_output.transpose(1, 2).contiguous().view(batch_size, -1, self.d_model)
        attention_output = self.W_out(attention_output)
        return attention_output

# Define Transformer Encoder Layer
class TransformerEncoderLayer(nn.Module):
    def __init__(self, d_model, num_heads):
        super(TransformerEncoderLayer, self).__init__()
        self.attention = MultiHeadSelfAttention(d_model, num_heads)
        self.norm1 = nn.LayerNorm(d_model)
        self.feed_forward = nn.Sequential(
            nn.Linear(d_model, 2048),
            nn.ReLU(),
            nn.Linear(2048, d_model)
        )
        self.norm2 = nn.LayerNorm(d_model)

    def forward(self, x):
        x_att = self.attention(x, x, x)
        x = self.norm1(x + x_att)
        x_ff = self.feed_forward(x)
        x = self.norm2(x + x_ff)
        return x



# Define Convolutional Transformer Classifier Model
class ConvolutionalTransformerClassifier(pl.LightningModule):
    def __init__(self, num_classes, d_model, num_heads, num_layers):
        super(ConvolutionalTransformerClassifier, self).__init__()
        self.conv_base = ConvolutionalBase1(512)
        self.transformer_layers = nn.ModuleList([
            TransformerEncoderLayer(d_model, num_heads) for _ in range(num_layers)
        ])
        self.cls_token = nn.Parameter(torch.randn(1, d_model))  # Remove the last dimension from cls_token
        self.fc = nn.Linear(2560, num_classes)  # Adjusted input size for fc layer #dmodel*4
    def forward(self, x):
      # Display the dimension before processing
      #print(f"Input Dimension: {x.size()}")

      x = self.conv_base(x)
      batch_size = x.size(0)
      cls_token = self.cls_token.expand(batch_size, -1, 512)  # Ensure cls_token matches the size along dimension 2

      # Concatenate cls_token and x along the feature dimension
      x = torch.cat((cls_token, x), dim=1)  # Concatenate along the feature dimension

      # Display the dimension after concatenation
      #print(f"Concatenated Dimension: {x.size()}")

      for layer in self.transformer_layers:
          x = layer(x)
      #print(x)
      x = x.flatten(start_dim=1)  # Flatten the input tensor along the feature dimension
      #x = x.reshape()
      x = self.fc(x)  # Pass through the fully connected layer
      return x




    def training_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        loss = F.cross_entropy(logits, y)
        self.log('train_loss', loss)
        return loss

    def validation_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        loss = F.cross_entropy(logits, y)
        self.log('val_loss', loss)
        preds = torch.argmax(logits, dim=1)
        acc = (preds == y).float().mean()
        self.log('val_acc', acc)

    def test_step(self, batch, batch_idx):
        x, y = batch
        logits = self(x)
        loss = F.cross_entropy(logits, y)
        self.log('test_loss', loss)
        preds = torch.argmax(logits, dim=1)
        acc = (preds == y).float().mean()
        self.log('test_acc', acc)

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(), lr=1e-3)
        return optimizer

num_classes = len(custom_data_module.training_dataset.categories)
d_model = 512
num_heads = 1  # Change to 2 or 4 for different number of attention heads
num_layers = 2
model = ConvolutionalTransformerClassifier(num_classes, d_model, num_heads, num_layers)
# Change the input dimension to match the final output shape of the transformer_layers
#model.fc = nn.Linear(512 * 8, 10)  # Adjust accordingly if output shape changes

# Train the Model
trainer = pl.Trainer(max_epochs=100, default_root_dir='./logs')
trainer.fit(model, custom_data_module)

# Test the Model
trainer.test(datamodule=custom_data_module)

num_head = 2
model_2head = ConvolutionalTransformerClassifier(num_classes, d_model, num_h, num_layers)

num_epochs = 100
train_model(model_2head, custom_data_module, criterion, optimizer, num_epochs)

# Evaluate the model on the validation set
evaluate_validation_set(model_2head, custom_data_module.val_dataloader())

# Evaluate the model on the test set
evaluate_test_set(model_2head, custom_data_module.test_dataloader())

num_head = 4
model_4head = ConvolutionalTransformerClassifier(num_classes, d_model, num_h, num_layers)

num_epochs = 100
train_model(model_4head, custom_data_module, criterion, optimizer, num_epochs)

# Evaluate the model on the validation set
evaluate_validation_set(model_4head, custom_data_module.val_dataloader())

# Evaluate the model on the test set
evaluate_test_set(model_4head, custom_data_module.test_dataloader())















