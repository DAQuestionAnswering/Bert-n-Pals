# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HugginFace Inc. team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""PyTorch BERT model."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import copy
import json
import math
import six
import torch
import torch.nn.functional as F
import torch.nn as nn
from torch.nn import CrossEntropyLoss, MSELoss
from torch.autograd import Variable
from torch.nn.parameter import Parameter


def gelu(x):
    """Implementation of the gelu activation function.
        For information: OpenAI GPT's gelu is slightly different (and gives slightly different results):
        0.5 * x * (1 + torch.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * torch.pow(x, 3))))
    """
    return x * 0.5 * (1.0 + torch.erf(x / math.sqrt(2.0)))


class BertConfig(object):
    """Configuration class to store the configuration of a `BertModel`.
    """
    def __init__(self,
                vocab_size,
                hidden_size=768,
                num_hidden_layers=12,
                num_attention_heads=12,
                intermediate_size=3072,
                hidden_act="gelu",
                hidden_dropout_prob=0.1,
                attention_probs_dropout_prob=0.1,
                max_position_embeddings=512,
                type_vocab_size=16,
                initializer_range=0.02,
                pals=False,
                mult=False,
                top=False,
                lhuc=False,
                houlsby=False,
                bert_lay_top=False,
                num_tasks=1,
                extra_dim=None,
                hidden_size_aug=204):
        """Constructs BertConfig.

        Args:
            vocab_size: Vocabulary size of `inputs_ids` in `BertModel`.
            hidden_size: Size of the encoder layers and the pooler layer.
            num_hidden_layers: Number of hidden layers in the Transformer encoder.
            num_attention_heads: Number of attention heads for each attention layer in
                the Transformer encoder.
            intermediate_size: The size of the "intermediate" (i.e., feed-forward)
                layer in the Transformer encoder.
            hidden_act: The non-linear activation function (function or string) in the
                encoder and pooler.
            hidden_dropout_prob: The dropout probabilitiy for all fully connected
                layers in the embeddings, encoder, and pooler.
            attention_probs_dropout_prob: The dropout ratio for the attention
                probabilities.
            max_position_embeddings: The maximum sequence length that this model might
                ever be used with. Typically set this to something large just in case
                (e.g., 512 or 1024 or 2048).
            type_vocab_size: The vocabulary size of the `token_type_ids` passed into
                `BertModel`.
            initializer_range: The sttdev of the truncated_normal_initializer for
                initializing all weight matrices.
        """
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.hidden_act = hidden_act
        self.intermediate_size = intermediate_size
        self.hidden_dropout_prob = hidden_dropout_prob
        self.attention_probs_dropout_prob = attention_probs_dropout_prob
        self.max_position_embeddings = max_position_embeddings
        self.type_vocab_size = type_vocab_size
        self.initializer_range = initializer_range
        self.hidden_size_aug = hidden_size_aug
        self.pals = pals
        self.extra_dim = extra_dim
        self.houlsby = houlsby
        self.mult = mult
        self.top = top
        self.bert_lay_top = bert_lay_top
        self.lhuc = lhuc
        self.num_tasks=num_tasks

    @classmethod
    def from_dict(cls, json_object):
        """Constructs a `BertConfig` from a Python dictionary of parameters."""
        config = BertConfig(vocab_size=None)
        for (key, value) in six.iteritems(json_object):
            config.__dict__[key] = value
        return config

    @classmethod
    def from_json_file(cls, json_file):
        """Constructs a `BertConfig` from a json file of parameters."""
        with open(json_file, "r") as reader:
            text = reader.read()
        return cls.from_dict(json.loads(text))

    def to_json_file(self, json_file_path):
        """ Save this instance to a json file."""
        with open(json_file_path, "w", encoding='utf-8') as writer:
            writer.write(self.to_json_string())

    def to_dict(self):
        """Serializes this instance to a Python dictionary."""
        output = copy.deepcopy(self.__dict__)
        return output

    def to_json_string(self):
        """Serializes this instance to a JSON string."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


class EsimConfig(object):
    """Configuration class to store the configuration of a `EsimModel`.
    """
    def __init__(self,
                vocab_size,
                weight_decay=0,
                grad_clipping=10,
                length_limit=512,
                dropout=0.1,
                hidden_size=100,
                word_dim=300):
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.weight_decay = weight_decay
        self.grad_clipping = grad_clipping
        self.length_limit = length_limit
        self.dropout = dropout
        self.word_dim = word_dim

    @classmethod
    def from_dict(cls, json_object):
        """Constructs a `EsimConfig` from a Python dictionary of parameters."""
        config = EsimConfig(vocab_size=None)
        for (key, value) in six.iteritems(json_object):
            config.__dict__[key] = value
        return config

    @classmethod
    def from_json_file(cls, json_file):
        """Constructs a `EsimConfig` from a json file of parameters."""
        with open(json_file, "r") as reader:
            text = reader.read()
        return cls.from_dict(json.loads(text))

    def to_json_file(self, json_file_path):
        """ Save this instance to a json file."""
        with open(json_file_path, "w", encoding='utf-8') as writer:
            writer.write(self.to_json_string())

    def to_dict(self):
        """Serializes this instance to a Python dictionary."""
        output = copy.deepcopy(self.__dict__)
        return output

    def to_json_string(self):
        """Serializes this instance to a JSON string."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


class BERTLayerNorm(nn.Module):
    def __init__(self, config, multi_params=None, variance_epsilon=1e-12):
        """Construct a layernorm module in the TF style (epsilon inside the square root).
        """
        super(BERTLayerNorm, self).__init__()
        if multi_params is not None:
            self.gamma = nn.Parameter(torch.ones(config.hidden_size_aug))
            self.beta = nn.Parameter(torch.zeros(config.hidden_size_aug))
        else:
            self.gamma = nn.Parameter(torch.ones(config.hidden_size))
            self.beta = nn.Parameter(torch.zeros(config.hidden_size))
        self.variance_epsilon = variance_epsilon

    def forward(self, x):
        u = x.mean(-1, keepdim=True)
        s = (x - u).pow(2).mean(-1, keepdim=True)
        x = (x - u) / torch.sqrt(s + self.variance_epsilon)
        return self.gamma * x + self.beta


class BERTEmbeddings(nn.Module):
    def __init__(self, config):
        super(BERTEmbeddings, self).__init__()
        """Construct the embedding module from word, position and token_type embeddings.
        """
        self.word_embeddings = nn.Embedding(config.vocab_size, config.hidden_size)
        self.position_embeddings = nn.Embedding(config.max_position_embeddings, config.hidden_size)
        self.token_type_embeddings = nn.Embedding(config.type_vocab_size, config.hidden_size)

        # self.LayerNorm is not snake-cased to stick with TensorFlow model variable name and be able to load
        # any TensorFlow checkpoint file
        self.LayerNorm = BERTLayerNorm(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)

    def forward(self, input_ids, token_type_ids=None):
        seq_length = input_ids.size(1)
        position_ids = torch.arange(seq_length, dtype=torch.long, device=input_ids.device)
        position_ids = position_ids.unsqueeze(0).expand_as(input_ids)
        if token_type_ids is None:
            token_type_ids = torch.zeros_like(input_ids)

        words_embeddings = self.word_embeddings(input_ids)
        position_embeddings = self.position_embeddings(position_ids)
        token_type_embeddings = self.token_type_embeddings(token_type_ids)

        embeddings = words_embeddings + position_embeddings + token_type_embeddings
        embeddings = self.LayerNorm(embeddings)
        embeddings = self.dropout(embeddings)
        return embeddings


class BERTSelfAttention(nn.Module):
    def __init__(self, config, multi_params=None):
        super(BERTSelfAttention, self).__init__()
        if config.hidden_size % config.num_attention_heads != 0:
            raise ValueError(
                "The hidden size (%d) is not a multiple of the number of attention "
                "heads (%d)" % (config.hidden_size, config.num_attention_heads))
        if multi_params is not None:
            self.num_attention_heads = multi_params
            self.attention_head_size = int(config.hidden_size_aug / self.num_attention_heads)
            self.all_head_size = self.num_attention_heads * self.attention_head_size
            hidden_size = config.hidden_size_aug
        else:
            self.num_attention_heads = config.num_attention_heads
            self.attention_head_size = int(config.hidden_size / config.num_attention_heads)
            self.all_head_size = self.num_attention_heads * self.attention_head_size
            hidden_size = config.hidden_size

        self.query = nn.Linear(hidden_size, self.all_head_size)
        self.key = nn.Linear(hidden_size, self.all_head_size)
        self.value = nn.Linear(hidden_size, self.all_head_size)

        self.dropout = nn.Dropout(config.attention_probs_dropout_prob)

    def transpose_for_scores(self, x):
        new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
        x = x.view(*new_x_shape)
        return x.permute(0, 2, 1, 3)

    def forward(self, hidden_states, attention_mask):
        mixed_query_layer = self.query(hidden_states)
        mixed_key_layer = self.key(hidden_states)
        mixed_value_layer = self.value(hidden_states)

        query_layer = self.transpose_for_scores(mixed_query_layer)
        key_layer = self.transpose_for_scores(mixed_key_layer)
        value_layer = self.transpose_for_scores(mixed_value_layer)

        # Take the dot product between "query" and "key" to get the raw attention scores.
        attention_scores = torch.matmul(query_layer, key_layer.transpose(-1, -2))
        attention_scores = attention_scores / math.sqrt(self.attention_head_size)
        # Apply the attention mask is (precomputed for all layers in BertModel forward() function)
        attention_scores = attention_scores + attention_mask

        # Normalize the attention scores to probabilities.
        attention_probs = nn.Softmax(dim=-1)(attention_scores)

        # This is actually dropping out entire tokens to attend to, which might
        # seem a bit unusual, but is taken from the original Transformer paper.
        attention_probs = self.dropout(attention_probs)

        context_layer = torch.matmul(attention_probs, value_layer)
        context_layer = context_layer.permute(0, 2, 1, 3).contiguous()
        new_context_layer_shape = context_layer.size()[:-2] + (self.all_head_size,)
        context_layer = context_layer.view(*new_context_layer_shape)
        return context_layer


class BERTMultSelfOutput(nn.Module):
    def __init__(self, config, multi_params=None):
        super(BERTMultSelfOutput, self).__init__()
        self.LayerNorm = BERTLayerNorm(config, multi_params)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)

    def forward(self, hidden_states, input_tensor):
        hidden_states = self.dropout(hidden_states)
        hidden_states = self.LayerNorm(hidden_states + input_tensor)
        return hidden_states


class BERTSelfOutput(nn.Module):
    def __init__(self, config, multi_params=None, houlsby=False):
        super(BERTSelfOutput, self).__init__()
        if houlsby:
            multi = BERTLowRank(config)
            self.multi_layers = nn.ModuleList([copy.deepcopy(multi) for _ in range(config.num_tasks)])    
        if multi_params is not None:
            self.dense = nn.Linear(config.hidden_size_aug, config.hidden_size_aug)
        else:
            self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.LayerNorm = BERTLayerNorm(config, multi_params)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.houlsby = houlsby

    def forward(self, hidden_states, input_tensor, attention_mask=None, i=0):
        hidden_states = self.dense(hidden_states)
        hidden_states = self.dropout(hidden_states)
        if self.houlsby:
            hidden_states = hidden_states + self.multi_layers[i](hidden_states, attention_mask)
        hidden_states = self.LayerNorm(hidden_states + input_tensor)
        return hidden_states


class BERTAttention(nn.Module):
    def __init__(self, config, multi_params=None, houlsby=False):
        super(BERTAttention, self).__init__()
        self.self = BERTSelfAttention(config, multi_params)
        self.output = BERTSelfOutput(config, multi_params, houlsby)

    def forward(self, input_tensor, attention_mask, i=0):
        self_output = self.self(input_tensor, attention_mask)
        attention_output = self.output(self_output, input_tensor, attention_mask, i=i)
        return attention_output


class BERTPals(nn.Module):
    def __init__(self, config, extra_dim=None):
        super(BERTPals, self).__init__()
        # Encoder and decoder matrices project down to the smaller dimension
        self.aug_dense = nn.Linear(config.hidden_size, config.hidden_size_aug)
        self.aug_dense2 = nn.Linear(config.hidden_size_aug, config.hidden_size)
        # Attention without the final matrix multiply.
        self.attn = BERTSelfAttention(config, 6)
        self.config = config
        self.hidden_act_fn = gelu

    def forward(self, hidden_states, attention_mask=None):
        hidden_states_aug = self.aug_dense(hidden_states)
        hidden_states_aug = self.attn(hidden_states_aug, attention_mask) 
        hidden_states = self.aug_dense2(hidden_states_aug)
        hidden_states = self.hidden_act_fn(hidden_states)
        return hidden_states


class BERTLowRank(nn.Module):
    def __init__(self, config, extra_dim=None):
        super(BERTLowRank, self).__init__()
        # Encoder and decoder matrices project down to the smaller dimension
        if config.extra_dim:
            self.aug_dense = nn.Linear(config.hidden_size, config.extra_dim)
            self.aug_dense2 = nn.Linear(config.extra_dim, config.hidden_size)
        else:
            self.aug_dense = nn.Linear(config.hidden_size, config.hidden_size_aug)
            self.aug_dense2 = nn.Linear(config.hidden_size_aug, config.hidden_size)
        self.config = config
        self.hidden_act_fn = gelu

    def forward(self, hidden_states, attention_mask=None):
        hidden_states_aug = self.aug_dense(hidden_states)
        hidden_states_aug = self.hidden_act_fn(hidden_states_aug)
        hidden_states = self.aug_dense2(hidden_states_aug)
        return hidden_states


class BERTIntermediate(nn.Module):
    def __init__(self, config):
        super(BERTIntermediate, self).__init__()
        self.dense = nn.Linear(config.hidden_size, config.intermediate_size)
        self.config = config
        self.intermediate_act_fn = gelu

    def forward(self, hidden_states):
        hidden_states = self.dense(hidden_states)
        hidden_states = self.intermediate_act_fn(hidden_states)
        return hidden_states


class BERTLhuc(nn.Module):
    def __init__(self, config):
        super(BERTLhuc, self).__init__()
        self.lhuc = Parameter(torch.zeros(config.hidden_size))

    def forward(self, hidden_states):
        hidden_states = hidden_states * 2. * nn.functional.sigmoid(self.lhuc)
        return hidden_states


class BERTOutput(nn.Module):
    def __init__(self, config, houlsby=False):
        super(BERTOutput, self).__init__()
        self.dense = nn.Linear(config.intermediate_size, config.hidden_size)
        self.LayerNorm = BERTLayerNorm(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        if houlsby:
            if config.pals:
                multi = BERTPals(config)
            else:
                multi = BERTLowRank(config)
            self.multi_layers = nn.ModuleList([copy.deepcopy(multi) for _ in range(config.num_tasks)])    
        self.houlsby = houlsby

    def forward(self, hidden_states, input_tensor, attention_mask=None, i=0):
        hidden_states = self.dense(hidden_states)
        hidden_states = self.dropout(hidden_states)
        if self.houlsby:
            hidden_states = hidden_states + self.multi_layers[i](input_tensor, attention_mask)
        hidden_states = self.LayerNorm(hidden_states + input_tensor)
        return hidden_states


class BERTLayer(nn.Module):
    def __init__(self, config, mult=False, houlsby=False):
        super(BERTLayer, self).__init__()
        self.attention = BERTAttention(config, houlsby=houlsby)
        self.intermediate = BERTIntermediate(config)
        self.output = BERTOutput(config, houlsby=houlsby)
        if config.lhuc:
            lhuc = BERTLhuc(config)
            self.multi_lhuc = nn.ModuleList([copy.deepcopy(lhuc) for _ in range(config.num_tasks)])
        if mult:
            if config.pals:
                multi = BERTPals(config)
            else:
                multi = BERTLowRank(config)
            self.multi_layers = nn.ModuleList([copy.deepcopy(multi) for _ in range(config.num_tasks)])    
        self.mult = mult
        self.lhuc = config.lhuc        
        self.houlsby = houlsby

    def forward(self, hidden_states, attention_mask, i=0):
        attention_output = self.attention(hidden_states, attention_mask, i)
        intermediate_output = self.intermediate(attention_output)
        if self.lhuc and not self.mult:
            layer_output = self.output(intermediate_output, attention_output)
            layer_output = self.multi_lhuc[i](layer_output)
        elif self.mult:
            extra = self.multi_layers[i](hidden_states, attention_mask)        
            if self.lhuc:
                extra = self.multi_lhuc[i](extra)
            layer_output = self.output(intermediate_output, attention_output + extra)
        elif self.houlsby:
            layer_output = self.output(intermediate_output, attention_output, attention_mask, i)
        else:
            layer_output = self.output(intermediate_output, attention_output)
        return layer_output


class BERTEncoder(nn.Module):
    def __init__(self, config):
        super(BERTEncoder, self).__init__()
        self.config = config
        if config.houlsby:
            # Adjust line below to add PALs etc. to different layers. True means add a PAL.
            self.multis = [True if i < 999 else False for i in range(config.num_hidden_layers)]
            self.layer = nn.ModuleList([BERTLayer(config, houlsby=mult) for mult in self.multis])    
        elif config.mult:
            # Adjust line below to add PALs etc. to different layers. True means add a PAL.
            self.multis = [True if i < 999 else False for i in range(config.num_hidden_layers)]
            self.layer = nn.ModuleList([BERTLayer(config, mult=mult) for mult in self.multis])    
        else:
            layer = BERTLayer(config)
            self.layer = nn.ModuleList([copy.deepcopy(layer) for _ in range(config.num_hidden_layers)])

        if config.top:
            if config.bert_lay_top:
                multi = BERTLayer(config)
            else:
                # Projection matrices and attention for adding to the top.
                mult_dense = nn.Linear(config.hidden_size, config.hidden_size_aug)
                self.mult_dense = nn.ModuleList([copy.deepcopy(mult_dense) for _ in range(config.num_tasks)])
                mult_dense2 = nn.Linear(config.hidden_size_aug, config.hidden_size)
                self.mult_dense2 = nn.ModuleList([copy.deepcopy(mult_dense2) for _ in range(config.num_tasks)])
                multi = nn.ModuleList([copy.deepcopy(BERTAttention(config, 12)) for _ in range(6)])

            self.multi_layers = nn.ModuleList([copy.deepcopy(multi) for _ in range(config.num_tasks)])
            self.gelu = gelu

        if config.mult and config.pals:
            dense = nn.Linear(config.hidden_size, config.hidden_size_aug)
            # Shared encoder and decoder across layers
            self.mult_aug_dense = nn.ModuleList([copy.deepcopy(dense) for _ in range(config.num_tasks)])
            dense2 = nn.Linear(config.hidden_size_aug, config.hidden_size)
            self.mult_aug_dense2 = nn.ModuleList([copy.deepcopy(dense2) for _ in range(config.num_tasks)])
            for l, layer in enumerate(self.layer):
                if self.multis[l]:
                    for i, lay in enumerate(layer.multi_layers):
                        lay.aug_dense = self.mult_aug_dense[i]
                        lay.aug_dense2 = self.mult_aug_dense2[i]
        if config.houlsby and config.pals:
            dense = nn.Linear(config.hidden_size, config.hidden_size_aug)
            # Shared encoder and decoder across layers
            self.mult_aug_dense = nn.ModuleList([copy.deepcopy(dense) for _ in range(config.num_tasks)])
            dense2 = nn.Linear(config.hidden_size_aug, config.hidden_size)
            self.mult_aug_dense2 = nn.ModuleList([copy.deepcopy(dense2) for _ in range(config.num_tasks)])
            dense3 = nn.Linear(config.hidden_size, config.hidden_size_aug)
            for l, layer in enumerate(self.layer):
                if self.multis[l]:
                    for i, lay in enumerate(layer.output.multi_layers):
                        lay.aug_dense = self.mult_aug_dense[i]
                        lay.aug_dense2 = self.mult_aug_dense2[i]


    def forward(self, hidden_states, attention_mask, i=0):
        all_encoder_layers = []
        for layer_module in self.layer:
            hidden_states = layer_module(hidden_states, attention_mask, i)
            all_encoder_layers.append(hidden_states)
        if self.config.top:
            if self.config.bert_lay_top:
                all_encoder_layers[-1] = self.multi_layers[i](hidden_states, attention_mask)
            else:
                hidden_states = self.mult_dense[i](hidden_states)
                for lay in self.multi_layers[i]:
                    hidden_states = lay(hidden_states, attention_mask)
                all_encoder_layers[-1] = self.mult_dense2[i](hidden_states)
        return all_encoder_layers


class BERTPooler(nn.Module):
    def __init__(self, config):
        super(BERTPooler, self).__init__()
        
        dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.activation = nn.Tanh()
        self.pool = False
        if self.pool:
            self.mult_dense_layers = nn.ModuleList([copy.deepcopy(dense) for _ in range(config.num_tasks)])
        else:
            self.dense = dense
        self.mult = config.mult
        self.top = config.top

    def forward(self, hidden_states, i=0):
        # We "pool" the model by simply taking the hidden state corresponding
        # to the first token.
        first_token_tensor = hidden_states[:, 0]
        if (self.mult or self.top) and self.pool:
            pooled_output = self.mult_dense_layers[i](first_token_tensor)
        else:
            pooled_output = self.dense(first_token_tensor)
        pooled_output = self.activation(pooled_output)
        return pooled_output


class BertModel(nn.Module):
    """BERT model ("Bidirectional Embedding Representations from a Transformer").

    Example usage:
    ```python
    # Already been converted into WordPiece token ids
    input_ids = torch.LongTensor([[31, 51, 99], [15, 5, 0]])
    input_mask = torch.LongTensor([[1, 1, 1], [1, 1, 0]])
    token_type_ids = torch.LongTensor([[0, 0, 1], [0, 2, 0]])

    config = modeling.BertConfig(vocab_size=32000, hidden_size=512,
        num_hidden_layers=8, num_attention_heads=6, intermediate_size=1024)

    model = modeling.BertModel(config=config)
    all_encoder_layers, pooled_output = model(input_ids, token_type_ids, input_mask)
    ```
    """
    def __init__(self, config: BertConfig):
        """Constructor for BertModel.

        Args:
            config: `BertConfig` instance.
        """
        super(BertModel, self).__init__()
        self.embeddings = BERTEmbeddings(config)
        self.encoder = BERTEncoder(config)
        self.pooler = BERTPooler(config)

    def forward(self, input_ids, token_type_ids=None, attention_mask=None, i=0):
        if attention_mask is None:
            attention_mask = torch.ones_like(input_ids)
        if token_type_ids is None:
            token_type_ids = torch.zeros_like(input_ids)

        # We create a 3D attention mask from a 2D tensor mask.
        # Sizes are [batch_size, 1, 1, from_seq_length]
        # So we can broadcast to [batch_size, num_heads, to_seq_length, from_seq_length]
        # this attention mask is more simple than the triangular masking of causal attention
        # used in OpenAI GPT, we just need to prepare the broadcast dimension here.
        extended_attention_mask = attention_mask.unsqueeze(1).unsqueeze(2)

        # Since attention_mask is 1.0 for positions we want to attend and 0.0 for
        # masked positions, this operation will create a tensor which is 0.0 for
        # positions we want to attend and -10000.0 for masked positions.
        # Since we are adding it to the raw scores before the softmax, this is
        # effectively the same as removing these entirely.
        extended_attention_mask = extended_attention_mask.float()
        extended_attention_mask = (1.0 - extended_attention_mask) * -10000.0

        embedding_output = self.embeddings(input_ids, token_type_ids)
        all_encoder_layers = self.encoder(embedding_output, extended_attention_mask, i)
        sequence_output = all_encoder_layers[-1]
        pooled_output = self.pooler(sequence_output, i)
        return all_encoder_layers, pooled_output


class BertForMultiTask(nn.Module):
    """BERT model for classification or regression on GLUE tasks (STS-B is treated as a regression task).
    This module is composed of the BERT model with a linear layer on top of
    the pooled output.

    ```
    """
    def __init__(self, config, tasks):
        super(BertForMultiTask, self).__init__()
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.classifier = nn.ModuleList([nn.Linear(config.hidden_size, num_labels) 
                                         for i, num_labels in enumerate(tasks)])
        def init_weights(module):
            if isinstance(module, (nn.Linear, nn.Embedding)):
                # Slightly different from the TF version which uses truncated_normal for initialization
                # cf https://github.com/pytorch/pytorch/pull/5617
                module.weight.data.normal_(mean=0.0, std=config.initializer_range)
            elif isinstance(module, BERTLayerNorm):
                module.beta.data.normal_(mean=0.0, std=config.initializer_range)
                module.gamma.data.normal_(mean=0.0, std=config.initializer_range)
            if isinstance(module, nn.Linear):
                if module.bias is not None:
                    module.bias.data.zero_()
        self.apply(init_weights)

    def forward(self, input_ids, token_type_ids, attention_mask, task_id, name='cola', labels=None):
        _, pooled_output = self.bert(input_ids, token_type_ids, attention_mask, task_id)
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier[task_id](pooled_output)

        if labels is not None and name != 'sts':
            loss_fct = CrossEntropyLoss()
            loss = loss_fct(logits, labels)
            return loss, logits
        # STS is a regression task.
        elif labels is not None and name == 'sts':
            loss_fct = MSELoss()
            loss = loss_fct(logits, labels.unsqueeze(1))
            return loss, logits
        else:
            return logits

class BertForMultiNLI(nn.Module):
    """BERT model for classification over sentence pair.
    This module is composed of the BERT model with a linear layer on top of
    the pooled output.
    ```
    """
    def __init__(self, config, task_num_labels):
        super(BertForMultiNLI, self).__init__()
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.classifier = nn.ModuleList([nn.Linear(config.hidden_size, num_labels) 
                                         for i, num_labels in enumerate(task_num_labels)])
        def init_weights(module):
            if isinstance(module, (nn.Linear, nn.Embedding)):
                # Slightly different from the TF version which uses truncated_normal for initialization
                # cf https://github.com/pytorch/pytorch/pull/5617
                module.weight.data.normal_(mean=0.0, std=config.initializer_range)
            elif isinstance(module, BERTLayerNorm):
                module.beta.data.normal_(mean=0.0, std=config.initializer_range)
                module.gamma.data.normal_(mean=0.0, std=config.initializer_range)
            if isinstance(module, nn.Linear):
                if module.bias is not None:
                    module.bias.data.zero_()
        self.apply(init_weights)

    def forward(self, input_ids, token_type_ids, attention_mask, task_id, labels=None):
        _, pooled_output = self.bert(input_ids, token_type_ids, attention_mask, task_id)
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier[task_id](pooled_output)

        if labels is not None:
            loss_fct = CrossEntropyLoss()
            loss = loss_fct(logits, labels)
            return loss, logits
        else:
            return logits

class BertForQuestionAnswering(nn.Module):
    """BERT model for Question Answering (span extraction).
    This module is composed of the BERT model with a linear layer on top of
    the sequence output that computes start_logits and end_logits

    Example usage:
    ```python
    # Already been converted into WordPiece token ids
    input_ids = torch.LongTensor([[31, 51, 99], [15, 5, 0]])
    input_mask = torch.LongTensor([[1, 1, 1], [1, 1, 0]])
    token_type_ids = torch.LongTensor([[0, 0, 1], [0, 2, 0]])

    config = BertConfig(vocab_size=32000, hidden_size=512,
        num_hidden_layers=8, num_attention_heads=6, intermediate_size=1024)

    model = BertForQuestionAnswering(config)
    start_logits, end_logits = model(input_ids, token_type_ids, input_mask)
    ```
    """
    def __init__(self, config):
        super(BertForQuestionAnswering, self).__init__()
        self.bert = BertModel(config)
        # TODO check with Google if it's normal there is no dropout on the token classifier of SQuAD in the TF version
        # self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.qa_outputs = nn.Linear(config.hidden_size, 2)

        def init_weights(module):
            if isinstance(module, (nn.Linear, nn.Embedding)):
                # Slightly different from the TF version which uses truncated_normal for initialization
                # cf https://github.com/pytorch/pytorch/pull/5617
                module.weight.data.normal_(mean=0.0, std=config.initializer_range)
            elif isinstance(module, BERTLayerNorm):
                module.beta.data.normal_(mean=0.0, std=config.initializer_range)
                module.gamma.data.normal_(mean=0.0, std=config.initializer_range)
            if isinstance(module, nn.Linear):
                module.bias.data.zero_()
        self.apply(init_weights)

    def forward(self, input_ids, token_type_ids, attention_mask, task_id=None, start_positions=None, end_positions=None):
        all_encoder_layers, _ = self.berppt(input_ids, token_type_ids, attention_mask, task_id)
        sequence_output = all_encoder_layers[-1]
        logits = self.qa_outputs(sequence_output)
        start_logits, end_logits = logits.split(1, dim=-1)
        start_logits = start_logits.squeeze(-1)
        end_logits = end_logits.squeeze(-1)

        if start_positions is not None and end_positions is not None:
            # If we are on multi-GPU, split add a dimension - if not this is a no-op
            start_positions = start_positions.squeeze(-1)
            end_positions = end_positions.squeeze(-1)
            # sometimes the start/end positions are outside our model inputs, we ignore these terms
            ignored_index = start_logits.size(1)
            start_positions.clamp_(0, ignored_index)
            end_positions.clamp_(0, ignored_index)

            loss_fct = CrossEntropyLoss(ignore_index=ignored_index)
            start_loss = loss_fct(start_logits, start_positions)
            end_loss = loss_fct(end_logits, end_positions)
            total_loss = (start_loss + end_loss) / 2
            return total_loss
        else:
            return start_logits, end_logits
    
    def load_pretained(self, init_checkpoint, patch=False):
        if patch:
            partial = torch.load(init_checkpoint, map_location='cpu')
            model_dict = self.bert.state_dict()
            update = {}
            for n, p in model_dict.items():
                if 'aug' in n or 'mult' in n:
                    update[n] = p
                    if 'pooler.mult' in n and 'bias' in n:
                        update[n] = partial['pooler.dense.bias']
                    if 'pooler.mult' in n and 'weight' in n:
                        update[n] = partial['pooler.dense.weight']
                else:
                    update[n] = partial[n]
            self.bert.load_state_dict(update)
        else:
            self.bert.load_state_dict(torch.load(init_checkpoint, map_location='cpu'))


class ESIM(nn.Module):
    """
    Implementation of the ESIM model presented in the paper "Enhanced LSTM for
    Natural Language Inference" by Chen et al.
    """

    def __init__(self, config, task_num_labels):
        """
        Args:
            word_dict_size: The size of the vocabulary of embeddings in the model.
            embedding_dim: The dimension of the word embeddings.
            hidden_size: The size of all the hidden layers in the network.
            embeddings: A tensor of size (vocab_size, embedding_dim) containing
                pretrained word embeddings. If None, word embeddings are
                initialised randomly. Defaults to None.
            padding_idx: The index of the padding token in the premises and
                hypotheses passed as input to the model. Defaults to 0.
            dropout: The dropout rate to use between the layers of the network.
                A dropout rate of 0 corresponds to using no dropout at all.
                Defaults to 0.5.
            num_classes: The number of classes in the output of the network.
                Defaults to 3.
        """
        super(ESIM, self).__init__()
        self.vocab_size = config.vocab_size
        self.embedding_dim = config.word_dim
        self.hidden_size = config.hidden_size
        self.num_classes = task_num_labels
        self.dropout = config.dropout

        self.word_embedding = nn.Embedding(self.vocab_size + 1,
                                           self.embedding_dim,
                                           padding_idx=0,
                                           _weight=None)

        if self.dropout:
            self._rnn_dropout = RNNDropout(p=self.dropout)

        self._encoding = StackedBRNN(self.embedding_dim, self.hidden_size, 1,
                                     dropout_rate=0, dropout_output=False, rnn_type=nn.LSTM,
                                     concat_layers=False, padding=False)

        self._attention = SoftmaxAttention()

        self._projection = nn.Sequential(nn.Linear(4*2*self.hidden_size,
                                                   self.hidden_size),
                                         nn.ReLU())

        self._composition = StackedBRNN(self.hidden_size, self.hidden_size, 1,
                                        dropout_rate=0, dropout_output=False, rnn_type=nn.LSTM,
                                        concat_layers=False, padding=False)

        self._classification = nn.Sequential(nn.Dropout(p=self.dropout),
                                             nn.Linear(2*4*self.hidden_size,
                                                       self.hidden_size),
                                             nn.Tanh(),
                                             nn.Dropout(p=self.dropout),
                                             nn.Linear(self.hidden_size,
                                                       self.num_classes))

        # Initialize all weights and biases in the model.
        self.apply(_init_esim_weights)

    def forward(self, input_ids, token_type_ids, attention_mask, task_id, labels=None):
        """
        Args:
            premises: A batch of varaible length sequences of word indices
                representing premises. The batch is assumed to be of size
                (batch, premises_length).
            hypothesis: A batch of varaible length sequences of word indices
                representing hypotheses. The batch is assumed to be of size
                (batch, hypotheses_length).

        Returns:
            logits: A tensor of size (batch, num_classes) containing the
                logits for each output class of the model.
            probabilities: A tensor of size (batch, num_classes) containing
                the probabilities of each output class in the model.
        """
        input_ids_list = list(torch.split(input_ids, int(attention_mask.size(1)/2), dim=1))
        premises = input_ids_list[0]
        hypotheses = input_ids_list[1]

        mask_list = list(torch.split(attention_mask, int(attention_mask.size(1)/2), dim=1))
        premises_mask = mask_list[0]
        hypotheses_mask = mask_list[1]

        Amask = torch.ByteTensor(premises.size(0), premises.size(1)).fill_(1)
        for i, d in enumerate(premises_mask):
            Amask[i, :sum(d.tolist())].fill_(0)
        Bmask = torch.ByteTensor(hypotheses.size(0), hypotheses.size(1)).fill_(1)
        for i, d in enumerate(hypotheses_mask):
            Bmask[i, :sum(d.tolist())].fill_(0)
        premises_mask = Amask.cuda()
        hypotheses_mask = Bmask.cuda()

        embedded_premises = self.word_embedding(premises)
        embedded_hypotheses = self.word_embedding(hypotheses)

        if self.dropout:
            embedded_premises = self._rnn_dropout(embedded_premises)
            embedded_hypotheses = self._rnn_dropout(embedded_hypotheses)

        encoded_premises = self._encoding(embedded_premises,
                                          premises_mask)
        encoded_hypotheses = self._encoding(embedded_hypotheses,
                                            hypotheses_mask)

        attended_premises, attended_hypotheses =\
            self._attention(encoded_premises, encoded_hypotheses,
                            premises_mask, hypotheses_mask)

        enhanced_premises = torch.cat([encoded_premises,
                                       attended_premises,
                                       encoded_premises - attended_premises,
                                       encoded_premises * attended_premises],
                                      dim=-1)
        enhanced_hypotheses = torch.cat([encoded_hypotheses,
                                         attended_hypotheses,
                                         encoded_hypotheses - attended_hypotheses,
                                         encoded_hypotheses * attended_hypotheses],
                                        dim=-1)

        projected_premises = self._projection(enhanced_premises)
        projected_hypotheses = self._projection(enhanced_hypotheses)

        if self.dropout:
            projected_premises = self._rnn_dropout(projected_premises)
            projected_hypotheses = self._rnn_dropout(projected_hypotheses)

        v_ai = self._composition(projected_premises, premises_mask)
        v_bj = self._composition(projected_hypotheses, hypotheses_mask)

        reversed_premises_mask = (1-premises_mask).float()
        reversed_hypotheses_mask = (1 - hypotheses_mask).float()

        v_a_avg = torch.sum(v_ai * reversed_premises_mask.unsqueeze(2), dim=1)\
            / torch.sum(reversed_premises_mask, dim=1, keepdim=True)
        v_b_avg = torch.sum(v_bj * reversed_hypotheses_mask.unsqueeze(2), dim=1)\
            / torch.sum(reversed_hypotheses_mask, dim=1, keepdim=True)

        v_ai = v_ai.masked_fill(premises_mask.unsqueeze(2), -1e7)
        v_bj = v_bj.masked_fill(hypotheses_mask.unsqueeze(2), -1e7)

        v_a_max, _ = v_ai.max(dim=1)
        v_b_max, _ = v_bj.max(dim=1)

        v = torch.cat([v_a_avg, v_a_max, v_b_avg, v_b_max], dim=1)

        logits = self._classification(v)
        if labels is not None:
            loss_fct = CrossEntropyLoss()
            loss = loss_fct(logits, labels)
            return loss, logits
        else:
            return logits


def _init_esim_weights(module):
    """
    Initialise the weights of the ESIM model.
    """
    if isinstance(module, nn.Linear):
        nn.init.xavier_uniform_(module.weight.data)
        nn.init.constant_(module.bias.data, 0.0)

    elif isinstance(module, nn.LSTM):
        nn.init.xavier_uniform_(module.weight_ih_l0.data)
        nn.init.orthogonal_(module.weight_hh_l0.data)
        nn.init.constant_(module.bias_ih_l0.data, 0.0)
        nn.init.constant_(module.bias_hh_l0.data, 0.0)
        hidden_size = module.bias_hh_l0.data.shape[0] // 4
        module.bias_hh_l0.data[hidden_size:(2*hidden_size)] = 1.0

        if (module.bidirectional):
            nn.init.xavier_uniform_(module.weight_ih_l0_reverse.data)
            nn.init.orthogonal_(module.weight_hh_l0_reverse.data)
            nn.init.constant_(module.bias_ih_l0_reverse.data, 0.0)
            nn.init.constant_(module.bias_hh_l0_reverse.data, 0.0)
            module.bias_hh_l0_reverse.data[hidden_size:(2*hidden_size)] = 1.0


class RNNDropout(nn.Dropout):
    """
    Dropout layer for the inputs of RNNs.

    Apply the same dropout mask to all the elements of the same sequence in
    a batch of sequences of size (batch, sequences_length, embedding_dim).
    """

    def forward(self, sequences_batch):
        """
        Apply dropout to the input batch of sequences.

        Args:
            sequences_batch: A batch of sequences of vectors that will serve
                as input to an RNN.
                Tensor of size (batch, sequences_length, emebdding_dim).

        Returns:
            A new tensor on which dropout has been applied.
        """
        ones = sequences_batch.data.new_ones(sequences_batch.shape[0],
                                             sequences_batch.shape[-1])
        dropout_mask = nn.functional.dropout(ones, self.p, self.training,
                                             inplace=False)
        return dropout_mask.unsqueeze(1) * sequences_batch


class StackedBRNN(nn.Module):
    """Stacked Bi-directional RNNs.
    Differs from standard PyTorch library in that it has the option to save
    and concat the hidden states between layers. (i.e. the output hidden size
    for each sequence input is num_layers * hidden_size).
    """
    def __init__(self, input_size, hidden_size, num_layers,
                 dropout_rate=0, dropout_output=False, rnn_type=nn.LSTM,
                 concat_layers=False, padding=False):
        super(StackedBRNN, self).__init__()
        self.padding = padding
        self.dropout_output = dropout_output
        self.dropout_rate = dropout_rate
        self.num_layers = num_layers
        self.concat_layers = concat_layers
        self.rnns = nn.ModuleList()
        for i in range(num_layers):
            input_size = input_size if i == 0 else 2 * hidden_size
            self.rnns.append(rnn_type(input_size, hidden_size,
                                      num_layers=1,
                                      bidirectional=True))

    def forward(self, x, x_mask):
        """Encode either padded or non-padded sequences.
        Can choose to either handle or ignore variable length sequences.
        Always handle padding in eval.
        Args:
            x: batch * len * hdim
            x_mask: batch * len (1 for padding, 0 for true)
        Output:
            x_encoded: batch * len * hdim_encoded
        """
        if x_mask.data.sum() == 0:
            # No padding necessary.
            output = self._forward_unpadded(x, x_mask)
        elif self.padding or not self.training:
            # Pad if we care or if its during eval.
            output = self._forward_padded(x, x_mask)
        else:
            # We don't care.
            output = self._forward_unpadded(x, x_mask)

        return output.contiguous()

    def _forward_unpadded(self, x, x_mask):
        """Faster encoding that ignores any padding."""
        # Transpose batch and sequence dims
        x = x.transpose(0, 1)

        # Encode all layers
        outputs = [x]
        for i in range(self.num_layers):
            rnn_input = outputs[-1]

            # Apply dropout to hidden input
            if self.dropout_rate > 0:
                rnn_input = F.dropout(rnn_input,
                                      p=self.dropout_rate,
                                      training=self.training)
            # Forward
            rnn_output = self.rnns[i](rnn_input)[0]
            outputs.append(rnn_output)

        # Concat hidden layers
        if self.concat_layers:
            output = torch.cat(outputs[1:], 2)
        else:
            output = outputs[-1]

        # Transpose back
        output = output.transpose(0, 1)

        # Dropout on output layer
        if self.dropout_output and self.dropout_rate > 0:
            output = F.dropout(output,
                               p=self.dropout_rate,
                               training=self.training)
        return output

    def _forward_padded(self, x, x_mask):
        """Slower (significantly), but more precise, encoding that handles
        padding.
        """
        # Compute sorted sequence lengths
        lengths = x_mask.data.eq(0).long().sum(1).squeeze()
        _, idx_sort = torch.sort(lengths, dim=0, descending=True)
        _, idx_unsort = torch.sort(idx_sort, dim=0)
        lengths = list(lengths[idx_sort])

        # Sort x
        x = x.index_select(0, idx_sort)

        # Transpose batch and sequence dims
        x = x.transpose(0, 1)

        # Pack it up
        rnn_input = nn.utils.rnn.pack_padded_sequence(x, lengths)

        # Encode all layers
        outputs = [rnn_input]
        for i in range(self.num_layers):
            rnn_input = outputs[-1]

            # Apply dropout to input
            if self.dropout_rate > 0:
                dropout_input = F.dropout(rnn_input.data,
                                          p=self.dropout_rate,
                                          training=self.training)
                rnn_input = nn.utils.rnn.PackedSequence(dropout_input,
                                                        rnn_input.batch_sizes)
            outputs.append(self.rnns[i](rnn_input)[0])

        # Unpack everything
        for i, o in enumerate(outputs[1:], 1):
            outputs[i] = nn.utils.rnn.pad_packed_sequence(o)[0]

        # Concat hidden layers or take final
        if self.concat_layers:
            output = torch.cat(outputs[1:], 2)
        else:
            output = outputs[-1]

        # Transpose and unsort
        output = output.transpose(0, 1)
        output = output.index_select(0, idx_unsort)

        # Pad up to original batch sequence length
        if output.size(1) != x_mask.size(1):
            padding = torch.zeros(output.size(0),
                                  x_mask.size(1) - output.size(1),
                                  output.size(2)).type(output.data.type())
            output = torch.cat([output, padding], 1)

        # Dropout on output layer
        if self.dropout_output and self.dropout_rate > 0:
            output = F.dropout(output,
                               p=self.dropout_rate,
                               training=self.training)
        return output


class SoftmaxAttention(nn.Module):
    """
    Attention layer taking premises and hypotheses encoded by an RNN as input
    and computing the soft attention between their elements.

    The dot product of the encoded vectors in the premises and hypotheses is
    first computed. The softmax of the result is then used in a weighted sum
    of the vectors of the premises for each element of the hypotheses, and
    conversely for the elements of the premises.
    """

    def forward(self, v1, v2, v1_mask=None, v2_mask=None):
        """
        Args:
            v1: A batch of sequences of vectors representing the
                premises in some NLI task. The batch is assumed to have the
                size (batch, sequences, vector_dim).
            v1_mask: A mask for the sequences in the premise batch, to
                ignore padding data in the sequences during the computation of
                the attention.
            v2: A batch of sequences of vectors representing the
                hypotheses in some NLI task. The batch is assumed to have the
                size (batch, sequences, vector_dim).
            v2_mask: A mask for the sequences in the hypotheses batch,
                to ignore padding data in the sequences during the computation
                of the attention.

        Returns:
            attended_premises: The sequences of attention vectors for the
                premises in the input batch.
            attended_hypotheses: The sequences of attention vectors for the
                hypotheses in the input batch.
        """
        similarity_matrix = v1.bmm(v2.transpose(2, 1).contiguous())

        prem_hyp_attn = F.softmax(similarity_matrix.masked_fill(v1_mask.unsqueeze(2), -float('inf')), dim=1)
        hyp_prem_attn = F.softmax(similarity_matrix.masked_fill(v2_mask.unsqueeze(1), -float('inf')), dim=2)

        attended_premises = hyp_prem_attn.bmm(v2)
        attended_hypotheses = prem_hyp_attn.transpose(1, 2).bmm(v1)

        attended_premises.masked_fill_(v1_mask.unsqueeze(2), 0)
        attended_hypotheses.masked_fill_(v2_mask.unsqueeze(2), 0)

        return attended_premises, attended_hypotheses
