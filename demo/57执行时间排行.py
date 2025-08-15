# 请修改编辑器中的代码，完成以下功能：在文件 out.txt 中，有一些数据库操作的执行时间信息，文件格式如下：

# starting,0.000037,2.102
# After opening tables,0.000008,0.455
# System lock,0.000004,0.227
# Table lock,0.000008,0.455
# …

# 其中第1列是操作名称，第2列是操作所花费的时间，第3列是该操作所占全部过程的百分比。字段之间用英文逗号 隔开
# 程序要求：

# 读取 out.txt 文件中的内容，统计所有操作的时间总和并输出。
# 输出操作时间占比最高的三个操作的百分比值及其对应的操作名称。

# 输出示例：
# the total execute time is 0.0017
# the top 0 percentage time is 46.023, spent in "Filling schema table"

# sumtime = 0
# percls = []
# ts = {}
# with open('out.txt', 'r') as f:

#         ...
# print('the total execute time is ', sumtime)

# tns = list(ts.items())
# tns.sort(key=lambda x: x[1], reverse=True)
# for i in range(3):
#     print('the top {} percentage time is {}, spent in "{}" operation'.format(i, tns[i][1],tns[i][0]))

#######################################################################################################################################

import turtle

turtle.pensize(2)
d = 0
for i in range(1, 6):
    turtle.fd(100)
    d += 72
    turtle.seth(d)
