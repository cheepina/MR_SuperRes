from torch.utils.data import Dataset,DataLoader
import torch
from UNetModel import Unet
from MRIBrainData import BrainDataset
import torch.optim as optim
import torch.nn as nn
from tqdm import tqdm
from mpl_toolkits.axes_grid1 import ImageGrid
from torch.utils.tensorboard import SummaryWriter
import matplotlib.pyplot as plt
import numpy as np
import os


'''
Parameters to avoid memory overflow error
'''
torch.cuda.empty_cache()
torch.backends.cudnn.benchmark = True
torch.backends.cudnn.deterministic = True
restore = False
'''
Checks for GPU and decides the device for processing
'''
device = "cuda" if torch.cuda.is_available() else "cpu"

'''
Initialize model
'''
def init_weights(m):
    if type(m) == nn.Conv3d:
        torch.nn.init.xavier_uniform_(m.weight)
    # m.bias.data.fill_(0.01)

unet3D = Unet(in_channel=1,out_channel=1,filters=2)
unet3D.apply(init_weights)
unet3D = unet3D.to(device)

'''
General Hyper parameters
'''
learning_rate = 0.001
Batch_Size = 1
opt = optim.Adam(unet3D.parameters(),lr=learning_rate)
loss_fn = nn.L1Loss()
Epochs = 10

'''
Initializes a Tensorboard summary writer to keep track of the training process
'''

training_name = "baseUnet3D_OriginalSize_ADAMOptim_{}Epochs_BS{}_GlorotWeights_L1Loss".format(Epochs,Batch_Size)
writer = SummaryWriter(os.path.join("runs",training_name))




'''
Training data, calls the BrainDataset(Custom Dataset Class)
'''
Training_dataset = BrainDataset("IXI-T1",Validation=False)
TrainLoader = DataLoader(Training_dataset,batch_size=Batch_Size)
'''
Testing data, calls the BrainDataset(Custom Dataset Class)
'''
Test_dataset  = BrainDataset ("IXI-T1",Validation= True)
TestLoader = DataLoader(Test_dataset,batch_size=1)

# unet3D = torch.load("first_training_ADAM_10EPOCHS.pth")

'''
Generated image from the writeImage method is the arranged and converted into a matplotlib figure and written on tensorboard
'''
def show(img,epoch,step):
    fig,ax = plt.subplots(1,3,figsize = (15,5))
    fig.suptitle("Epoch {}".format(epoch+1))
    ax[0].imshow(img[0],interpolation='nearest',origin="lower",cmap="gray")
    ax[0].set_title("Original")
    ax[0].set_axis_off()
    ax[1].imshow(img[1], interpolation='nearest', origin="lower", cmap="gray")
    ax[1].set_title("Reduced")
    ax[1].set_axis_off()
    ax[2].imshow(img[2], interpolation='nearest', origin="lower", cmap="gray")
    ax[2].set_title("Predicted")
    ax[2].set_axis_off()
    writer.add_figure("comparison",fig,step)


'''
changes the model to the evaluation mode and feed forwards Test data into the model, Generates a resultant image
'''

def writeImage(epoch,step):
    unet3D.eval()
    original,reduced = Test_dataset[0]
    original = torch.from_numpy(original).to(device)
    reduced = torch.from_numpy(np.expand_dims(reduced,0)).to(device)
    pred = unet3D(reduced)
    original,reduced,pred = torch.squeeze(original),torch.squeeze(reduced),torch.squeeze(pred)
    slice_original = (original[:, :, int(original.shape[2] / 2)])
    slice_reduced  = (reduced[:,: ,int(reduced.shape[2]/2)])
    slice_pred = (pred[:,:,int(pred.shape[2]/2)])
    slices_list = [slice_original.detach().cpu().numpy().T,slice_reduced.detach().cpu().numpy().T,slice_pred.detach().cpu().numpy().T]
    show(slices_list,epoch,step)
    unet3D.train()

'''
The Training loop begins here
'''
step = 0
print("Beginning Training............")
Batch_count = len(TrainLoader)

'''
Restoring checkpoint since the training has been interupted
'''
if restore:
    checkpoint = torch.load("Models/baseUnet3D_OriginalSize__ADAMOptim_10Epochs_BS4.pth")
    unet3D.load_state_dict(checkpoint["model_state_dict"])
    opt.load_state_dict(checkpoint['optimizer_state_dict'])
    epoch = checkpoint["epoch"]

for epoch in range(Epochs):
    torch.cuda.empty_cache()
    overall_loss = 0
    for idx,(original,reduced) in enumerate(tqdm(TrainLoader)):
        step += 1
        original = original.to(device)
        reduced = reduced.to(device)
        logit = unet3D(reduced)
        loss = loss_fn(logit,original)
        opt.zero_grad()
        loss.backward()
        opt.step()
        overall_loss += loss.item()
        writer.add_scalar("training_loss",loss.item(),step)

    writeImage(epoch, step)
    print("EPOCH {} Loss ====> {}".format(epoch,overall_loss/Batch_count))
    torch.save({
        'epoch': epoch,
        'model_state_dict': unet3D.state_dict(),
        'optimizer_state_dict': opt.state_dict(),
        'loss': overall_loss/Batch_count,
    }, os.path.join("Models",training_name))

'''
saves the model after training
'''
torch.save(unet3D,os.path.join("Models",training_name))

