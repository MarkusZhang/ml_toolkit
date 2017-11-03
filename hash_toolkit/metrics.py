"""
this includes the computation for precision, recall, MAP
"""
#TODO: add MAP measure
import itertools
import io
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

def _pyplot_to_image(plt_obj):
    "return a PIL.Image object"
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    im = Image.open(buf)
    return im


def _fig2data(fig):
    """
    @brief Convert a Matplotlib figure to a 4D numpy array with RGBA channels and return it
    @param fig a matplotlib figure
    @return a numpy 3D array of RGBA values
    """
    # draw the renderer
    fig.canvas.draw()
    # Get the RGBA buffer from the figure
    w, h = fig.canvas.get_width_height()
    buf = np.fromstring(fig.canvas.tostring_argb(), dtype=np.uint8)
    buf.shape = (w, h, 4)
    # canvas.tostring_argb give pixmap in ARGB mode. Roll the ALPHA channel to have it in RGBA mode
    buf = np.roll(buf, 3, axis=2)
    return buf


def _fig2img (fig):
    """
    @brief Convert a Matplotlib figure to a PIL Image in RGBA format and return it
    @param fig a matplotlib figure
    @return a Python Imaging Library ( PIL ) image
    """
    # put the figure pixmap into a numpy array
    buf = _fig2data (fig)
    w, h, d = buf.shape
    return Image.frombytes( "RGBA", ( w ,h ), buf.tostring( ) )

def process_hash_csv(file_path,delimiter=","):
    "return list of {'label':..,'hash':'010101'}"
    results = []
    with open(file_path,"r") as f:
        lines = f.readlines()[1:]
        for line in lines:
            filename,label,hashcode = line.strip().split(delimiter)
            hashcode = hashcode.replace(" ","")
            results.append({"label":label,"hash":hashcode})
    return results

def _compute_hash_with_dist(hashcode, dist):
    "`hashcode` should only contain '0' and '1', return a list of hash strings, whose hamming distance to `hashcode` is `dist`"
    hash_ls = []
    invert = lambda x:"1" if x=="0" else "0"
    code_length = len(hashcode)
    for positions in itertools.combinations(range(code_length),dist):
        # invert the hash bit at `positions`
        computed_code = "".join([invert(hashcode[i]) if i in positions else hashcode[i]
                                 for i in range(code_length)])
        hash_ls.append(computed_code)

    return hash_ls

def _compute_hash_within_radius(hashcode, radius):
    "return list of hash strings, `hashcode` should be binary string '0101..'"
    hash_ls = []
    for i in range(radius+1):
        hash_ls += _compute_hash_with_dist(hashcode=hashcode, dist=i)
    return hash_ls

def _retrieve_items_using_hash(db_set, hashcode):
    "return a list of {'label':..,'hash':..}, retrieved from `db_set`, `db_set` should be list of dict"
    return [item for item in db_set if item["hash"]==hashcode]

def _get_hdist(code1, code2):
    "return hamming distance"
    assert len(code1) == len(code2)
    return len([1 for i in range(len(code1)) if code1[i]!=code2[i]])


def calculate_precision(radius,db_set,test_set):
    """
    :param radius:
    :param db_set: the data acting as the database, list of dict {"label":..,"hash":""}
    :param test_set: list of dict {"label":..,"hash":""}
    :return: the averaged precision over `test_set`
    """
    avg_precision = 0
    for item in test_set:
        query_hash = item["hash"]
        query_label = item["label"]
        # retrieve items from `db_set`
        hashes_within_radius = _compute_hash_within_radius(query_hash, radius)
        retrieved_items = []
        for hashcode in hashes_within_radius:
            retrieved_items += _retrieve_items_using_hash(db_set=db_set, hashcode=hashcode)

        # calculate precision for this test item
        num_correctly_retrieved = len([item for item in retrieved_items if item["label"]==query_label])
        if (len(retrieved_items) > 0 ):
            precision = num_correctly_retrieved * 1.0 / len(retrieved_items)
        else:
            precision = 0

        avg_precision += precision / len(test_set)

    return avg_precision


def get_mean_avg_precision(test_set,db_set,maxdist):
    """
    refer to https://i.ytimg.com/vi/pM6DJ0ZZee0/maxresdefault.jpg for formula
    :param test_set:list of dict {"label":..,"hash":""}
    :param db_set:list of dict {"label":..,"hash":""}
    :param maxdist:
    :return: mean average precision
    """
    m_a_p = 0
    for query in test_set:
        m_a_p += _get_avg_precision_for_query(query=query,db_set=db_set,maxdist=maxdist)
    return m_a_p / len(test_set)

def _get_avg_precision_for_query(query, db_set, maxdist):
    """
    refer to https://i.ytimg.com/vi/pM6DJ0ZZee0/maxresdefault.jpg for formula
    :param query: list of {hash:"101",label:".."}
    :param db_set: list of {hash:"101",label:".."}
    :param maxdist: maximum distance to retrieve
    :return: average precision for this single query
    """
    query_code = query["hash"]
    query_label = query["label"]
    avg_precision = 0
    num_added = 0
    total_retrieved = 0
    correct_retrieved = 0
    for d in range(maxdist):
        hash_ls = _compute_hash_with_dist(hashcode=query_code,dist=d)
        retrieved_items = []
        include = False # include precision at this distance when there is correct item retrieved
        for hash in hash_ls:
            retrieved_items = _retrieve_items_using_hash(db_set=db_set,hashcode=hash)
            total_retrieved += len(retrieved_items)
            new_correct = len([t for t in retrieved_items if t["label"]==query_label])
            if (new_correct > 0):
                correct_retrieved +=new_correct
                include = True

        if (include):
            num_added += 1
            avg_precision += float(correct_retrieved) / total_retrieved

    return avg_precision / num_added


def get_precision_vs_recall(test_set,db_set,max_hdist):
    """
    :param test_set: list of dict {"label":..,"hash":""}
    :param db_set: the data acting as the database
    :param max_hdist: maximum hamming distance two hash code can have
    :return: a list of {"precisions":[precision@dist0,precision@dist1,...],"recalls":[recall@dist0,recall@dist1...]}
    """
    results = []
    # for each test item, there is a precision list and recall list
    for i in range(len(test_set)):
        item = test_set[i]
        query_hash = item["hash"]
        query_label = item["label"]
        record_dict = {i:{"correct":0,"wrong":0} for i in range(max_hdist+1)}
        # loop through the db_set
        total_class_num = 0 # how many items in db have the same label as query_label
        for db_item in db_set:
            db_item_hash = db_item["hash"]
            hdist = _get_hdist(query_hash, db_item_hash)
            if (db_item["label"] == query_label):
                record_dict[hdist]["correct"] += 1
                total_class_num += 1
            else:
                record_dict[hdist]["wrong"] += 1

        # compute precisions and recalls
        total_correct = 0
        total_retrieved = 0
        precisions = []
        recalls = []
        for key,value in record_dict.items():
            total_correct += value["correct"]
            total_retrieved += value["correct"] + value["wrong"]
            if (total_retrieved>0):
                precisions.append(total_correct / total_retrieved)
            else:
                precisions.append(0)
            recalls.append(total_correct/total_class_num)

        print("finish item {}/{}".format(i,len(test_set)))
        # add to results
        results.append({"precisions":precisions,"recalls":recalls})
    return  results


def plot_avg_precision_vs_recall(pr_list):
    """
    :param pr_list: list of {"precisions":[],"recalls":[]}, output of `get_precision_vs_recall`
    :return: {"avg_precisions":[],"avg_recalls":[],"plot":Image object}
    """
    for item in pr_list:
        assert len(item["precisions"]) ==len(item["recalls"])

    valuelen = len(pr_list[0]["precisions"])
    avg_precisions = []
    avg_recalls = []
    for i in range(valuelen):
        # calculate avg precision, recall at hamming distance = i
        avg_p = 0
        avg_r = 0
        for item in pr_list:
            avg_p += item["precisions"][i] / len(pr_list)
            avg_r += item["recalls"][i] / len(pr_list)
        avg_precisions.append(avg_p)
        avg_recalls.append(avg_r)

    fig = plt.figure()
    figplt = fig.add_subplot(111)
    figplt.plot(avg_recalls,avg_precisions)
    plt.xlabel("recall")
    plt.ylabel("precision")
    plt.title("Precision vs. Recall for 16-bit hash")
    plt.show()
    image = _fig2img(fig=fig)
    return {"avg_precisions":avg_precisions,"avg_recalls":avg_recalls,"plot":image}
