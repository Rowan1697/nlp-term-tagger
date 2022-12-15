import evaluate  # huggingface
from transformers import Trainer, TrainingArguments, DataCollatorForTokenClassification
from CRFDataLoader import PreDataCollator
import torch
import os

os.environ["WANDB_DISABLED"] = "true"  # weights and biases, weird message

class CustomTrainer:

    def __init__(self, model, train_dataset, eval_dataset, labels_to_ids, epochs=7, lr=1e-04):
        self.model = model
        self.tokenizer = model.tokenizer
        self.train_dataset = train_dataset
        self.eval_dataset = eval_dataset
        self.tokenized_data(labels_to_ids)

        self.epochs = epochs
        self.learning_rate = lr
        self.train_batch_size = 8
        self.val_batch_size = 8
        self.save_steps = 50
        self.eval_steps = 50
        self.save_limit = 2
        self.warmup_steps = 100
        self.grad_acc_steps = 2
        self.max_len = 256
        
    def tokenized_data(self, labels_to_ids):
        collator = PreDataCollator(tokenizer=self.model.tokenizer, max_len=self.max_len, tags_to_ids=labels_to_ids)
        self.train_dataset = self.train_dataset.map(collator, batch_size=4, num_proc=4, batched=True)
        self.eval_dataset = self.eval_dataset.map(collator, batch_size=4, num_proc=4, batched=True)
        

    def model_trainer(self, output_path):
        data_collator = DataCollatorForTokenClassification(self.tokenizer, return_tensors="pt")

        training_args = TrainingArguments(output_dir=output_path,
                                          group_by_length=True,
                                          per_device_train_batch_size=self.train_batch_size,
                                          gradient_accumulation_steps=self.grad_acc_steps,
                                          evaluation_strategy="steps",
                                          num_train_epochs=self.epochs,
                                          fp16=False,
                                          save_steps=self.save_steps,
                                          eval_steps=self.eval_steps,
                                          logging_steps=self.eval_steps,
                                          learning_rate=self.learning_rate,
                                          warmup_steps=self.warmup_steps,
                                          save_total_limit=self.save_limit)

        trainer = Trainer(model=self.model,# may need data_collator
                          data_collator=data_collator,
                          args=training_args,
                          compute_metrics = self.compute_metrics,
                          train_dataset=self.train_dataset,
                          eval_dataset=self.eval_dataset,
                          tokenizer=self.tokenizer)
        trainer.train()

    def compute_metrics(self, pred):
    
        metric_acc = evaluate.load("accuracy")
        metric_f1 = evaluate.load("f1")
    
        pred_logits = pred.predictions
        pred_ids = torch.tensor(pred_logits)
    
        tr_active_acc = torch.from_numpy(pred.label_ids != -100)
        pr_active_acc = torch.from_numpy(pred_logits != -100)
    
        train_labels = torch.masked_select(torch.from_numpy(pred.label_ids), tr_active_acc)
        train_predicts = torch.masked_select(pred_ids, pr_active_acc)
    
        acc = metric_acc.compute(predictions=train_predicts, references=train_labels)
        f1 = metric_f1.compute(predictions=train_predicts, references=train_labels, average="macro")
    
        return {"accuracy": acc["accuracy"], "f1": f1["f1"]}

class CustomEval(CustomTrainer):

    def __init__(self, model, labels_to_ids, test_set):

        self.model = model
        self.max_len = 128
        self.tokenized_data(labels_to_ids)
        self.test_dataset = test_set
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def tokenized_data(self, labels_to_ids):
        collator = PreDataCollator(tokenizer=self.model.tokenizer, max_len=self.max_len, tags_to_ids=labels_to_ids)
        self.test_dataset = self.train_dataset.map(collator, batch_size=4, num_proc=4, batched=True)
        

    def compute_metrics(self, preds, labels):
    
        metric_acc = evaluate.load("accuracy")
        metric_f1 = evaluate.load("f1")
        tr_active_acc = labels != -100
        pr_active_acc = preds != -100
        
        tags = torch.masked_select(labels, tr_active_acc)
        predicts = torch.masked_select(preds, pr_active_acc)

        acc = metric_acc.compute(predictions=predicts, references=tags)
        f1 = metric_f1.compute(predictions=predicts, references=tags, average="macro")
    
        return {"accuracy": acc["accuracy"], "f1": f1["f1"]}

    def evaluating(self):

        acc = 0
        f1 = 0
        size_dataset = len(self.test_data)

        for i in range(size_dataset):
            label_ids = torch.Tensor([self.test_data[i]["labels"]]).to(device)
            input_ids = torch.Tensor([self.test_data[i]["input_ids"]]).to(device)
            mask = torch.Tensor([self.test_data[i]["attention_mask"]]).to(device)
            _, logits = self.model(input_ids=input_ids, attention_mask=mask, labels=label_ids, return_dict=False)
            result = self.compute_metrics(logits, label_ids)
            acc += result["accuracy"]
            f1 += result["f1"]

        print("Accuracy: " + str(acc/size_dataset) + "\nF1: " + str(f1/size_dataset))
