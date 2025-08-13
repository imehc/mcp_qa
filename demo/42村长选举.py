# 请修改编辑器中的代码，完成以下功能，使用字典和列表型变量模拟村长选举：

# 某村有40名具有选举权和被选举权的村民，名单保存在 name.txt 文件中。从这40名村民中选出一人当村长，投票信息保存在 vote.txt 文件中，每行是一张选票的信息。有效票中得票最多的村民当选。程序需要实现下面两个功能：

# 一：请从 vote.txt 中筛选出无效票并写入文件 vote1.txt。有效票的含义是：选票中只有一个名字且该名字在 name.txt 文件列表中，不符合此条件的票即为无效票。

# 二：统计有效票中得票最多的村民，输出当选村长的名字及其得票数。


# f=open("name.txt")
# names=f.readlines()
# f.close()
# f=open("vote.txt")
# votes=f.readlines()
# f.close()
# f.close()
# f=open("vote1.txt","w")
# D={}
# NUM=0
# for vote in _______(1)________:
#     num = len(vote.split())
#     if num==1 and vote in _______(2)________:
#         D[vote[:-1]]=_______(3)________+1
#         NUM+=1
#     else:
#         f.write(_______(4)________)
# f.close()
# l=list(D.items())
# l.sort(key=lambda s:s[1],_______(5)________)
# name=____(6)____
# score=____(7)____
# print("有效票数为：{} 当选村长村民为:{},票数为：{}".format(NUM,name,score))

#######################################################################################################################################å

import turtle

turtle.pensize(2)
d = 0
for i in range(1, 9):
    turtle.fd(100)
    d += 45
    turtle.seth(d)
