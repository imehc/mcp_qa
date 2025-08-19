# 今天中午，你的外卖被偷了，你一怒之下来到了监控室开始查监控，请修改编辑器中的代码，读入 监控摄像数据.txt 文件中的数据，提取出监控器编号为earpa001的所有数据，并将结果输出保存到earpa001.txt文件。文件sensor.txt的内容示例如下：

# 2016/5/31 0:05, vawelon001,1,1
# 2016/5/31 0:20, earpa001,1,1
# 2016/5/31 2:26, earpa001,1,6

# 其中，第一列是监控器获取数据的时间，第二列是监控器的编号，第三列是监控器所在的楼层，第四列是监控器所在的位置区域编号。输出文件的格式要求为：每一行记录与原数据文件保持一致，行尾无空格，无空行。

# 参考格式：

# 2016/5/31 7:11, earpa001,2,4
# 2016/5/31 8:02, earpa001,3,4
# 2016/5/31 9:22, earpa001,3,4

# ...
# for line in ______:
# ...
#     fo.write('{},{},{},{}\n'.format(______))
# ...


#######################################################################################################################################
import jieba

def print_result(year):
    fa = open("./demo/66data{}.txt".format(year), "r")
    txt = fa.read()  # 读取文件内容
    fa.close()  # 关闭文件
    # 使用jieba分词，将文本内容切分为词语
    words = jieba.lcut(txt)
    # 统计词语出现次数，长度为1的词语忽略
    d = {}
    for word in words:
        if len(word) == 1:
            continue
        else:
            d[word] = d.get(word, 0) + 1  # 如果词语已存在字典中，计数加1；否则初始化为1
    lt = list(d.items())
    lt.sort(key=lambda x: x[1], reverse=True)
    return lt[:10]


da = print_result(2019)
db = print_result(2018)
# print(list(map(lambda x: x[0], da)))
# print(list(map(lambda x: x[0], db)))
d = {}

for i in range(10):
    for j in range(10):
        if da[i][0] == db[j][0]:
            d[da[i][0]] = da[i][1]

print("共有词语：{}".format(",".join(d.keys())))
print(
    "2019特有：{}".format(
        ",".join(list(map(lambda x: x[0], filter(lambda x: x[0] not in d, da))))
    )
)
print(
    "2018特有：{}".format(
        ",".join(list(map(lambda x: x[0], filter(lambda x: x[0] not in d, db))))
    )
)
