import copy
import torch
import numpy as np

def index_to_tag(labels, MAX_SEQ_LENGTH=96):
    
    """convert a batch of label indices to list of tags"""
    
    #define index to tag mapping
    indexMap = {0:'B', 1:'I', 2:'O'}
    
    #reshape labels to batch_size*MAX_SEQ_LENGTH
    
    labels = labels.reshape((-1,MAX_SEQ_LENGTH))
    
    batchTags = []
    
    #convert label index to tags
    for batch in labels:
    
        tags = [indexMap[idx.item()] for idx in batch]
        # tags = [indexMap[idx] for idx in batch]
        
        batchTags.append(tags)
    
    return batchTags

def index_to_token(token_ids, VOCAB):
    
    """convert a batch of token indices to list of strings"""
    
    batchSent = []
    
    for item in token_ids:
    
        sent = [VOCAB[idx-1] if idx < len(VOCAB) else 'UNK' for idx in item if idx!=0]
        
        batchSent.append(sent)
    
    return batchSent


def print_predictions(tokens, pred_tags, true_tags, VOCAB, MAX_SEQ_LENGTH=96):
    
    
    batch_tokens = index_to_token(tokens, VOCAB)
      
    batch_pred_tags = index_to_tag(pred_tags, MAX_SEQ_LENGTH)
    
    batch_true_tags = index_to_tag(true_tags, MAX_SEQ_LENGTH)
        
    
    from colorama import Style, Back
    
    outputs = []
    
    preds = []
    
    true = []
    
    for tokens,true_tags,pred_tags in zip(batch_tokens,batch_pred_tags,batch_true_tags):
        
        true_tags = true_tags[:len(tokens)]
        pred_tags = pred_tags[:len(tokens)]
        
        output = []
    
        for t,tl,pl in zip(tokens,true_tags,pred_tags):

            assert len(tokens) == len(pred_tags) == len(true_tags)

            if tl == pl:
                o = f"{t} {Back.GREEN}[{tl}][{pl}]{Style.RESET_ALL}"

            else:
                o = f"{t} {Back.GREEN}[{tl}]{Style.RESET_ALL}{Back.RED}[{pl}]{Style.RESET_ALL}"


            output.append(o)
            
        outputs.append(" ".join(output))
        preds.append(pred_tags)
        true.append(true_tags)
    
    return outputs, preds, true


def eval_crf(model, outputs, labels, batch=8, max_sequence_length=96, device = 'cpu'):

    num_class = outputs.shape[-1]

    batch = int(np.prod(outputs.shape)/(max_sequence_length*num_class))


    outputs = outputs.reshape(batch,max_sequence_length,num_class)

    flat_labels = labels.reshape(-1,num_class)
    pad_index=[1 if flat_labels[i].sum()!=0 else 0 for i in range(flat_labels.shape[0])]
    mask = torch.FloatTensor(pad_index)
    mask = mask.to(device)
    mask = mask.reshape(batch,max_sequence_length)

    labels = torch.argmax(labels, dim=-1).to(device)
        
    
    best_path = model.crf_layer.viterbi_tags(outputs, mask)
    predictions = np.zeros(labels.shape)

    best_path = [ids for ids,_ in best_path]

    # true_labels = [labels[i][:len(best_path[i])].tolist() for i in range(labels.shape[0])]
    for i in range(predictions.shape[0]):
        predictions[i][:len(best_path[i])] = best_path[i]
        
    # print(predictions)

    return labels, torch.tensor(predictions).to(device)
    



def eval(model, eval_dataloader, VOCAB=None, MAX_SEQ_LENGTH=96, device='cpu', return_predictions = False, CRF=False):
    
    model = copy.deepcopy(model)
    # Set the model in 'evaluation' mode (this disables some layers (batch norm, dropout...) which are not needed when testing)
    model.eval() 
    
    predictions = []

    # In evaluation phase, we don't need to compute gradients (for memory efficiency)
    with torch.no_grad():
        # initialize the total and correct number of labels to compute the accuracy
        correct_labels = 0
        total_labels = 0
        
        # Iterate over the dataset using the dataloader
        for batch in eval_dataloader:

            #get sentences and labels
            sent = batch['token_ids']
            labels = batch['labels']

            #get number of class or tags
            num_class = labels.shape[-1]
    
            #find the padded tokens
            padx = (sent > 0).float()
            
            #reshape it to make it as the same shape with labels
            padx = padx.reshape(-1)

            #count non-pad tokens
            num_tokens = padx.sum().item()
        
            #count padded tokens
            num_pad_tokens = padx.shape[0] - num_tokens
            

            
            if CRF:
                out = model(sent)
                labels, label_predicted = eval_crf(model, out, labels, len(batch), MAX_SEQ_LENGTH,device)
                # predictions.append(print_predictions(sent,label_predicted,labels, VOCAB, MAX_SEQ_LENGTH))


            else:

                # Get the predicted labels
                y_predicted = model(sent)
                # To get the predicted labels, we need to get the max over all possible classes
                # multiply with padx to ignore padded token predictions 
                label_predicted = torch.argmax(y_predicted.data, 1)*padx

                #reshape it to make it as the same shape with model output
                labels = labels.reshape(-1,num_class)
                labels = torch.argmax(labels, 1)*padx
                    
                # print(labels)

            # Compute accuracy: count the total number of samples,
            #and the correct labels (compare the true and predicted labels)
                
            total_labels += num_tokens #only added the non-padded tokens in count
            
            # subtract the padded tokens to ignore padded token predictions in final count
            correct_labels += ((label_predicted == labels).sum().item() - num_pad_tokens)
        
            accuracy = 100 * correct_labels / total_labels
            # get output
            if return_predictions:
                predictions.append(print_predictions(sent,label_predicted,labels, VOCAB, MAX_SEQ_LENGTH))
                
            
        if return_predictions:
            return 0, predictions
        
        return accuracy
