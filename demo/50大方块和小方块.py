# 请修改编辑器中的代码，完成以下功能：使用 turtle 库和 random 库，绘制四个彩色的正方形。正方形的颜色从颜色列表 color 中随机选择，边长在 [50,200] 之间随机选取。每个正方形的左下角坐标 (x, y) 从 [-100,100] 范围中随机选择。

# import turtle as t
# _______（1）______
# color = ['red','blue','purple','black']
# r.seed(1)
# for j in range(4):
#     t.pencolor(color[_______（2）______])
#     t.penup()
#     t.goto(r.randint(-100,100), _______（3）______)
#     t.pendown()
#     ra = r.randint(50, 200)
#     for i in range(_______（4）______):
#         t.fd(_______（5）______)
#         t.seth(90*i)
# t.done()

#######################################################################################################################################

data = input()

age_sum = 0
man_count = 0
count = 0

while data:
    if len(data.split()) == 3:
        name, sex, age = data.split()
        age_sum += int(age)
        count += 1
        if sex == "男":
            man_count += 1
    data = input()

average_age = age_sum / count
print("平均年龄是{:.2f} 男性人数是{}".format(average_age, man_count))