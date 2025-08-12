# 请修改编辑器中的代码，完成以下功能：以 123 为随机数种子，随机生成10个在1（含）到999（含）之间的随机数，数字之间用逗号分隔，屏幕输出这10个随机数。
# import random
# ______
# for i in range(______):
#     print(______, end=",")


#######################################################################################################################################
import random as r

r.seed(1)
s = input("请输入三个整数 n,m,k：")
slist = s.split(",")
num_list = range(int(slist[2]), int(slist[1]) + 1)
for i in r.sample(num_list, int(slist[0])):
    print(i)
