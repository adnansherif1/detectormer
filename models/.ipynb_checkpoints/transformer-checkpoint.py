from __future__ import print_function

import warnings
import numpy as np
from tensorflow.keras.utils import to_categorical
from sklearn.metrics import confusion_matrix
from sklearn.utils import compute_class_weight
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, LSTM, Bidirectional, ReLU
from tensorflow.keras.optimizers import Adamax
from tensorflow.keras.layers import Layer
from tensorflow.keras import backend as K
from tensorflow.keras import initializers, regularizers, constraints
from sklearn.model_selection import train_test_split
from parser import parameter_parser
from models.loss_draw import LossHistory
from tensorflow.keras import layers
args = parameter_parser()

warnings.filterwarnings("ignore")

"""
Bidirectional LSTM neural network with attention
"""


# def dot_product(x, kernel):
#     """
#     Wrapper for dot product operation, in order to be compatible with both Theano and Tensorflow
#     Args:
#         x (): input
#         kernel (): weights
#     Returns:
#     """
#     if K.backend() == 'tensorflow':
#         return K.squeeze(K.dot(x, K.expand_dims(kernel)), axis=-1)
#     else:
#         return K.dot(x, kernel)


# class AttentionWithContext(Layer):
#     """
#     Attention operation, with a context/query vector, for temporal data.
#     Supports Masking.
#     follows these equations:
#     (1) u_t = tanh(W h_t + b)
#     (2) \alpha_t = \frac{exp(u^T u)}{\sum_t(exp(u_t^T u))}, this is the attention weight
#     (3) v_t = \alpha_t * h_t, v in time t
#     # Input shape
#         3D tensor with shape: `(samples, steps, features)`.
#     # Output shape
#         3D tensor with shape: `(samples, steps, features)`.
#     """

#     def __init__(self,
#                  W_regularizer=None, u_regularizer=None, b_regularizer=None,
#                  W_constraint=None, u_constraint=None, b_constraint=None,
#                  bias=True, **kwargs):

#         self.supports_masking = True
#         self.init = initializers.get('glorot_uniform')

#         self.W_regularizer = regularizers.get(W_regularizer)
#         self.u_regularizer = regularizers.get(u_regularizer)
#         self.b_regularizer = regularizers.get(b_regularizer)

#         self.W_constraint = constraints.get(W_constraint)
#         self.u_constraint = constraints.get(u_constraint)
#         self.b_constraint = constraints.get(b_constraint)

#         self.bias = bias
#         super(AttentionWithContext, self).__init__(**kwargs)

#     def build(self, input_shape):
#         assert len(input_shape) == 3

#         self.W = self.add_weight((input_shape[-1], input_shape[-1],),
#                                  initializer=self.init,
#                                  name='{}_W'.format(self.name),
#                                  regularizer=self.W_regularizer,
#                                  constraint=self.W_constraint)
#         if self.bias:
#             self.b = self.add_weight((input_shape[-1],),
#                                      initializer='zero',
#                                      name='{}_b'.format(self.name),
#                                      regularizer=self.b_regularizer,
#                                      constraint=self.b_constraint)

#         self.u = self.add_weight((input_shape[-1],),
#                                  initializer=self.init,
#                                  name='{}_u'.format(self.name),
#                                  regularizer=self.u_regularizer,
#                                  constraint=self.u_constraint)

#         super(AttentionWithContext, self).build(input_shape)

#     def compute_mask(self, input, input_mask=None):
#         # do not pass the mask to the next layers
#         return None

#     def call(self, x, mask=None):
#         uit = dot_product(x, self.W)

#         if self.bias:
#             uit += self.b

#         uit = K.tanh(uit)
#         ait = dot_product(uit, self.u)

#         a = K.exp(ait)

#         # apply mask after the exp. will be re-normalized next
#         if mask is not None:
#             # Cast the mask to floatX to avoid float64 upcasting in theano
#             a *= K.cast(mask, K.floatx())

#         # in some cases especially in the early stages of training the sum may be almost zero and this results in NaN's.
#         # Should add a small epsilon as the workaround
#         # a /= K.cast(K.sum(a, axis=1, keepdims=True), K.floatx())
#         a /= K.cast(K.sum(a, axis=1, keepdims=True) + K.epsilon(), K.floatx())

#         a = K.expand_dims(a)
#         weighted_input = x * a

#         return weighted_input

#     def compute_output_shape(self, input_shape):
#         return input_shape[0], input_shape[1], input_shape[2]


# class Addition(Layer):
#     """
#     This layer is supposed to add of all activation weight.
#     We split this from AttentionWithContext to help us getting the activation weights
#     follows this equation:
#     (1) v = \sum_t(\alpha_t * h_t)

#     # Input shape
#         3D tensor with shape: `(samples, steps, features)`.
#     # Output shape
#         2D tensor with shape: `(samples, features)`.
#     """

#     def __init__(self, **kwargs):
#         super(Addition, self).__init__(**kwargs)

#     def build(self, input_shape):
#         self.output_dim = input_shape[-1]
#         super(Addition, self).build(input_shape)

#     def call(self, x):
#         return K.sum(x, axis=1)

#     def compute_output_shape(self, input_shape):
#         return (input_shape[0], self.output_dim)
class TransformerBlock(Layer):
    def __init__(self, embed_dim, num_heads, ff_dim, rate=0.1):
        super(TransformerBlock, self).__init__()
        self.att = layers.MultiHeadAttention(num_heads=num_heads, key_dim=embed_dim)
        self.ffn = keras.Sequential(
            [layers.Dense(ff_dim, activation="relu"), layers.Dense(embed_dim),]
        )
        self.layernorm1 = layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = layers.LayerNormalization(epsilon=1e-6)
        self.dropout1 = layers.Dropout(rate)
        self.dropout2 = layers.Dropout(rate)

    def call(self, inputs, training):
        attn_output = self.att(inputs, inputs)
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(inputs + attn_output)
        ffn_output = self.ffn(out1)
        ffn_output = self.dropout2(ffn_output, training=training)
        return self.layernorm2(out1 + ffn_output)

class TokenAndPositionEmbedding(Layer):
    def __init__(self, maxlen, vocab_size, embed_dim):
        super(TokenAndPositionEmbedding, self).__init__()
        # self.token_emb = layers.Embedding(input_dim=vocab_size, output_dim=embed_dim)
        self.pos_emb = layers.Embedding(input_dim=maxlen, output_dim=embed_dim)

    def call(self, x):
        maxlen = tf.shape(x)[-1]
        positions = tf.range(start=0, limit=maxlen, delta=1)
        positions = self.pos_emb(positions)
        # x = self.token_emb(x)
        return x + positions
    

class transformer:
    def __init__(self, data, name="", batch_size=args.batch_size, lr=args.lr, epochs=args.epochs, dropout=args.dropout):
        vectors = np.stack(data.iloc[:, 1].values)
        labels = data.iloc[:, 0].values
        positive_idxs = np.where(labels == 1)[0]
        negative_idxs = np.where(labels == 0)[0]
        undersampled_negative_idxs = np.random.choice(negative_idxs, len(positive_idxs), replace=False)
        resampled_idxs = np.concatenate([positive_idxs, undersampled_negative_idxs])
        idxs = np.concatenate([positive_idxs, negative_idxs])

        x_train, x_test, y_train, y_test = train_test_split(vectors[idxs], labels[idxs],
                                                            test_size=0.99, stratify=labels[idxs])

        self.x_train = x_train
        self.x_test = x_test
        self.y_train = to_categorical(y_train)
        self.y_test = to_categorical(y_test)
        self.name = name
        self.batch_size = batch_size
        self.epochs = epochs
        self.class_weight = compute_class_weight(class_weight='balanced', classes=[0, 1], y=labels)
        model = Sequential()
        # model.add(Bidirectional(LSTM(300, return_sequences=True), input_shape=(vectors.shape[1], vectors.shape[2])))
        # model.add(AttentionWithContext())
        # model.add(Addition())
        model.add(TokenAndPositionEmbedding(vectors.shape[1], vectors.shape[2], 300))
        model.add(TransformerBlock(300, 10, 300))
        model.add(layers.GlobalAveragePooling1D())
        model.add(ReLU())
        model.add(Dropout(dropout))
        model.add(Dense(300))
        model.add(ReLU())
        model.add(Dropout(dropout))
        model.add(Dense(2, activation='softmax'))
        # Lower learning rate to prevent divergence
        adamax = Adamax(lr)
        model.compile(adamax, 'categorical_crossentropy', metrics=['accuracy'])
        self.model = model

    """
    Trains model
    """

    def train(self):
        history = LossHistory()
        self.model.fit(self.x_train, self.y_train, batch_size=self.batch_size, epochs=self.epochs,
                       class_weight=self.class_weight, verbose=1, callbacks=[history], validation_data=(self.x_test, self.y_test))
        self.model.save_weights(self.name + "_model.pkl")
        history.loss_plot('epoch')

    """
    Tests accuracy of model
    Loads weights from file if no weights are attached to model object
    """

    def test(self):
        # self.model.load_weights("reentrancy_code_snippets_2000_model.pkl")
        values = self.model.evaluate(self.x_test, self.y_test, batch_size=self.batch_size, verbose=1)
        print("Accuracy: ", values[1])
        predictions = (self.model.predict(self.x_test, batch_size=self.batch_size)).round()

        tn, fp, fn, tp = confusion_matrix(np.argmax(self.y_test, axis=1), np.argmax(predictions, axis=1)).ravel()
        print('False positive rate(FP): ', fp / (fp + tn))
        print('False negative rate(FN): ', fn / (fn + tp))
        recall = tp / (tp + fn)
        print('Recall: ', recall)
        precision = tp / (tp + fp)
        print('Precision: ', precision)
        print('F1 score: ', (2 * precision * recall) / (precision + recall))
