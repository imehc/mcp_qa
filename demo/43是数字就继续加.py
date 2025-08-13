# 请修改编辑器中的代码，完成以下功能：
# 不断获取用户输入，要求输入内容不包含数字。
# 如果用户的输入中存在数字，则提示重新输入，直到输入的内容全部为非数字字符。
# 输入符合条件后，输出用户输入字符的总个数。

# 输入示例：
# abc123
# 输出示例：
# 请重新输入

# 输入示例：
# hello world
# 输出示例：
# 输入字符数为：11
# while True:
#     s = input("请输入不带数字的文本:")
#     ...
# print(len(s))

#######################################################################################################################################å

f = open("./demo/42name.txt")
names = f.readlines()
f.close()
f = open("./demo/42vote.txt")
votes = f.readlines()
f.close()
f.close()
f = open("./demo/42vote1.txt", "w")
D = {}
NUM = 0
for vote in votes:
    num = len(vote.split())  # 分解成列表，并求列表长度（元素个数）
    if num == 1 and vote in names:  # 仅一个且在姓名中，有效
        D[vote[:-1]] = D.get(vote[:-1], 0) + 1
        NUM += 1
    else:
        f.write(vote)
f.close()
l = list(D.items())
l.sort(key=lambda s: s[1], reverse=True)
name = l[0][0]
score = l[0][1]
print("有效票数为：{} 当选村长村民为:{},票数为：{}".format(NUM, name, score))
