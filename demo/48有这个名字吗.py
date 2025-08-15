# 请修改编辑器中的代码，完成以下功能：
# 定义一个包含若干名字字符串的列表 persons。
# 在该列表中查找用户输入的名字字符串：
# 如果找到该名字，则生成一个四位数字组成的随机验证码，并输出该名字和验证码。
# 如果未找到，则输出提示“对不起，您输入的名字不存在。”
# 若用户输入字母 q，则退出程序。
# 显示提示信息后再次显示“请输入一个名字：”提示用户输入，重复执行步骤2。程序在用户输入3次后自动退出。

# 示例：
# 假设 persons = ['Alice', 'John', 'Sarah', 'David']

# 输入示例：
# Alice
# 输出示例：
# Alice 2456

# 输入示例：
# Emma
# 输出示例：
# 对不起，您输入的名字不存在。

# 输入示例：
# q
# 输出示例：
# 程序自动退出

# import random as r
# r.seed(0)
# persons = ['Aele', 'Bob','lala', 'baicai']
# flag = 3
# while flag>0:
#     flag -= 1
#     ……
#         print('{} {}'.format(name, num))
#     ……
#         print('对不起，您输入的名字不存在。')

#######################################################################################################################################å

import turtle as t
import random as r

color = ["red", "orange", "blue", "green", "purple"]
r.seed(1)
for i in range(5):
    rad = r.randint(20, 50)
    x0 = r.randint(-100, 100)
    y0 = r.randint(-100, 100)
    t.color(r.choice(color))
    t.penup()
    t.goto(x0, y0)
    t.pendown()
    t.circle(rad)
t.done()
