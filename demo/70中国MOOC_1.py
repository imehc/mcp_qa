# 请修改编辑器中的代码，从 data.txt 文件中提取大学或机构名称列表，并按大学或机构在 data.txt 中出现的顺序写入文件 univ.txt，每行一个大学或机构名称。

# 提示：
# 大学名称在 data.txt 文件中以 alt="北京大学" 的形式存在。

# 输出文件示例（univ.txt 内容）：

# 北京大学
# 南京大学

# f = open("univ.txt", "w")

# ____________  # 此处可多行

# f.close()


#######################################################################################################################################

f = open("./demo/69earpa001.txt", "r")
fo = open("./demo/69earpa001_count.txt", "w")
d = {}
for line in f:
    t = line.strip(" \n").split(",")
    s = t[2] + "-" + t[3]
    d[s] = d.get(s, 0) + 1
ls = list(d.items())
ls.sort(key=lambda x: x[1], reverse=False)  # 该语句用于排序
for i in range(len(ls)):
    a, b = ls[i]
    fo.write("{},{}\n".format(a, b))
f.close()
fo.close()
