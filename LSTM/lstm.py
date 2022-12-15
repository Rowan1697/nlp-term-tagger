
from torch.utils.data import DataLoader
import torch
import numpy as np
import torch.nn as nn
import random
from torch.utils.data import DataLoader
import copy
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import classification_report
from entityDataset import EntityDataset
from model import RNN
from model_crf import RNN_CRF
from args import create_arg_parser
from train import train_step
from eval import eval



def training_lstm(model, train_dataloader, valid_dataloader, num_epochs, learning_rate, device='cpu',verbose=True):

    # Make a copy of the model (avoid changing the model outside this function)
    model_tr = copy.deepcopy(model)
    
    
    # Set the model in 'training' mode (ensures all parameters' gradients are computed - it's like setting 'requires_grad=True' for all parameters)
    model_tr.train()
    
    # Define the optimizer
    optimizer = torch.optim.Adam(model_tr.parameters(), lr=learning_rate)
    
    # Initialize lists to record the training loss over epochs
    loss_all_epochs = []
    val_loss_all_epochs = []
    
    best_accuracy = 0.0
    
    
    accuracy = []
    
    
    # Training loop
    for epoch in range(num_epochs):
        # Initialize the training loss for the current epoch
        loss_current_epoch = train_step(model_tr, train_dataloader, optimizer)
        val_loss_epoch = train_step(model_tr, valid_dataloader, optimizer, validation=True)


        acc = eval(model_tr, valid_dataloader,device=device)
        
        accuracy.append(acc)
        if acc > best_accuracy:
            best_accuracy = acc
            torch.save(model_tr.state_dict(), 'model_opt.pt')
            
        
        
        if verbose:
            print('Epoch [{}/{}],Train Loss: {:.4f} Val Loss: {:.4f}'.format(epoch+1, num_epochs, loss_current_epoch, val_loss_epoch))
        
    return model_tr, loss_all_epochs ,accuracy


def main():


    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    args = create_arg_parser()

    VECTOR_PATH = args.vector_path
    EMB_DIMENSION = args.embedding_size
    MAX_SEQ_LENGTH = args.seq_length

    SEED = 42

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    dataset_train = EntityDataset('../Dataset/train',VECTOR_PATH, EMB_DIMENSION,MAX_SEQ_LENGTH,  device)
    dataset_test = EntityDataset('../Dataset/test',VECTOR_PATH,EMB_DIMENSION, MAX_SEQ_LENGTH, device)
    dataset_dev = EntityDataset('../Dataset/dev',VECTOR_PATH,EMB_DIMENSION, MAX_SEQ_LENGTH, device)
    

    VOCAB = dataset_train.vocab


    batch_size = args.batch
    train_dataloader = DataLoader(dataset_train, batch_size=batch_size, shuffle=True)
    test_dataloader = DataLoader(dataset_test, batch_size=batch_size, shuffle=True)
    valid_dataloader = DataLoader(dataset_dev, batch_size=batch_size, shuffle=True)


    #the vocab size that is built from train set
    vocab_size = len(dataset_train.vocab)
    # the embedding dimenstion 50/100/300
    emb_dim = EMB_DIMENSION
    # get the embedding matrix
    word_embeddings = dataset_train.word_embeddings
    # max sequence length
    max_sequence_length = MAX_SEQ_LENGTH

    #define lstm layers
    num_layers = args.layers
    #define hidden size
    hidden_size = args.hidden_size
    #set if LSTM should be bidirectional 
    bidirectional = False
    # output size i.e class size 
    output_size = 3
    # activation function
    act_fn = nn.LogSoftmax(dim=-1)

    use_crf = args.use_crf

    # create a RNN  model instance. REMARK: remove .cuda() at the end if gpu is not available
    
    if use_crf:
        rnn = RNN_CRF(vocab_size, emb_dim, word_embeddings, max_sequence_length, 
            num_layers,hidden_size, bidirectional, output_size, act_fn, device)
    else:
        rnn = RNN(vocab_size, emb_dim, word_embeddings, max_sequence_length, 
            num_layers,hidden_size, bidirectional, output_size, act_fn, device)

    # 


    rnn.to(device)

    # number of epochs
    num_epochs = args.epoch
    # learning rate
    learning_rate = args.learning_rate

    # train model
    model_tr, loss_all_epochs, accuracy = training_lstm(rnn, train_dataloader, valid_dataloader, num_epochs, learning_rate, device)


    acc, preds = eval(model_tr,test_dataloader,VOCAB, MAX_SEQ_LENGTH, device, True, use_crf)
    outputs=[]
    pred_labels=[]
    true_labels = []
    true_spans = []
    pred_spans = []
    for o,p,t in preds:
        outputs.extend(o)
        
        for i in range(len(p)):
            pred_labels.extend(p[i])
            true_labels.extend(t[i])
            true_spans.append(" ".join(p[i]))
            pred_spans.append(" ".join(t[i]))


    print("#"*50)
    print('Token Level Evaluation')
    print(classification_report(pred_labels,true_labels))
    print("#"*50)

    df = pd.DataFrame()
    df['true'] = true_spans
    df['preds'] = pred_spans

    df.to_csv('outputs.csv',index=False)

    # for i, out in enumerate(outputs[:3]):
    #     print(out)
    #     print('\n')





if __name__ == '__main__':
    main()